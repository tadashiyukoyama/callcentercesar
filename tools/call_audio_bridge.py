from __future__ import annotations

import argparse
import os
import queue
import signal
import sys
import threading
import time
from pathlib import Path


PACKAGE_DIR = Path(
    os.environ.get("CALL_AUDIO_PACKAGES", r"D:\Tools\CallAudioBridge\python-packages")
)
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

import numpy as np
import sounddevice as sd


DEFAULT_PHONE_NAME = "Redmi 13"
DEFAULT_USB_NAME = "USB PnP Sound Device"
HFP_RATE = 16_000
USB_RATE = 48_000
HFP_FRAMES = 320
USB_FRAMES = 960


def find_device(host_api: str, name_fragment: str, direction: str, prefix: str | None = None) -> int:
    host_apis = sd.query_hostapis()
    matches: list[int] = []
    for index, device in enumerate(sd.query_devices()):
        name = str(device["name"])
        host_name = str(host_apis[device["hostapi"]]["name"])
        channels = device["max_input_channels"] if direction == "input" else device["max_output_channels"]
        if host_name != host_api or channels < 1 or name_fragment.casefold() not in name.casefold():
            continue
        if prefix and not name.casefold().startswith(prefix.casefold()):
            continue
        matches.append(index)
    if len(matches) != 1:
        raise RuntimeError(
            f"Esperava exatamente um dispositivo {direction} para {name_fragment!r} em {host_api}; "
            f"encontrei {matches}"
        )
    return matches[0]


def put_latest(target: queue.Queue[np.ndarray], samples: np.ndarray) -> None:
    try:
        target.put_nowait(samples)
        return
    except queue.Full:
        pass
    try:
        target.get_nowait()
    except queue.Empty:
        pass
    try:
        target.put_nowait(samples)
    except queue.Full:
        pass


def fit_block(samples: np.ndarray, frames: int) -> np.ndarray:
    if samples.size == frames:
        return samples
    if samples.size > frames:
        return samples[:frames]
    return np.pad(samples, (0, frames - samples.size))


def peak_percent(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.max(np.abs(samples.astype(np.int32)))) * 100.0 / 32768.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Ponte local Redmi HFP <-> headset USB")
    parser.add_argument("--duration", type=float, default=0.0, help="Segundos; zero mantem ate Ctrl+C")
    parser.add_argument(
        "--phone-name",
        default=DEFAULT_PHONE_NAME,
        help="Trecho do nome do endpoint HFP do celular",
    )
    parser.add_argument(
        "--usb-name",
        default=DEFAULT_USB_NAME,
        help="Trecho do nome do headset USB",
    )
    args = parser.parse_args()

    usb_output = find_device("Windows WASAPI", args.usb_name, "output")
    usb_input = find_device("Windows WASAPI", args.usb_name, "input")
    hfp_output = find_device("Windows WDM-KS", args.phone_name, "output", "Output (")
    hfp_input = find_device("Windows WDM-KS", args.phone_name, "input", "Input (")

    print(
        f"devices usb_out={usb_output} usb_in={usb_input} hfp_out={hfp_output} hfp_in={hfp_input}",
        flush=True,
    )

    phone_to_usb: queue.Queue[np.ndarray] = queue.Queue(maxsize=12)
    usb_to_phone: queue.Queue[np.ndarray] = queue.Queue(maxsize=12)
    stats_lock = threading.Lock()
    stats = {
        "phone_peak": 0.0,
        "usb_mic_peak": 0.0,
        "phone_underflow": 0,
        "usb_underflow": 0,
        "callback_status": 0,
    }

    def note_status(status: sd.CallbackFlags) -> None:
        if status:
            with stats_lock:
                stats["callback_status"] += 1

    def phone_duplex_callback(indata, outdata, frames, time_info, status) -> None:
        del time_info
        note_status(status)
        incoming = np.frombuffer(indata, dtype=np.int16).copy()
        with stats_lock:
            stats["phone_peak"] = max(stats["phone_peak"], peak_percent(incoming))
        put_latest(phone_to_usb, incoming)

        try:
            outgoing = usb_to_phone.get_nowait()
        except queue.Empty:
            outgoing = np.zeros(frames, dtype=np.int16)
            with stats_lock:
                stats["phone_underflow"] += 1
        outdata[:] = fit_block(outgoing, frames).astype(np.int16, copy=False).tobytes()

    def usb_duplex_callback(indata, outdata, frames, time_info, status) -> None:
        del time_info
        note_status(status)
        microphone = fit_block(np.frombuffer(indata, dtype=np.int16).copy(), frames)
        usable = microphone[: microphone.size - (microphone.size % 3)]
        downsampled = np.rint(usable.astype(np.int32).reshape(-1, 3).mean(axis=1)).astype(np.int16)
        with stats_lock:
            stats["usb_mic_peak"] = max(stats["usb_mic_peak"], peak_percent(microphone))
        put_latest(usb_to_phone, downsampled)

        try:
            incoming = phone_to_usb.get_nowait()
        except queue.Empty:
            incoming = np.zeros(HFP_FRAMES, dtype=np.int16)
            with stats_lock:
                stats["usb_underflow"] += 1
        incoming = fit_block(incoming, max(1, frames // 3))
        mono = fit_block(np.repeat(incoming, 3), frames)
        stereo = np.column_stack((mono, mono)).astype(np.int16, copy=False)
        outdata[:] = stereo.tobytes()

    wasapi_shared = sd.WasapiSettings(exclusive=False, auto_convert=True)
    streams = [
        sd.RawStream(
            device=(hfp_input, hfp_output),
            samplerate=HFP_RATE,
            channels=(1, 1),
            dtype="int16",
            blocksize=HFP_FRAMES,
            latency="low",
            callback=phone_duplex_callback,
        ),
        sd.RawStream(
            device=(usb_input, usb_output),
            samplerate=USB_RATE,
            channels=(1, 2),
            dtype="int16",
            blocksize=USB_FRAMES,
            latency="low",
            extra_settings=wasapi_shared,
            callback=usb_duplex_callback,
        ),
    ]

    stopped = threading.Event()

    def request_stop(signum, frame) -> None:
        del signum, frame
        stopped.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    started: list[sd.Stream] = []
    try:
        for stream in streams:
            stream.start()
            started.append(stream)
        print("bridge=running", flush=True)
        deadline = time.monotonic() + args.duration if args.duration > 0 else None
        while not stopped.wait(1.0):
            with stats_lock:
                snapshot = dict(stats)
                stats["phone_peak"] = 0.0
                stats["usb_mic_peak"] = 0.0
            print(
                "phone_in={phone_peak:.2f}% usb_mic={usb_mic_peak:.2f}% "
                "usb_underflow={usb_underflow} phone_underflow={phone_underflow} "
                "callback_status={callback_status}".format(**snapshot),
                flush=True,
            )
            if deadline is not None and time.monotonic() >= deadline:
                break
    finally:
        for stream in reversed(started):
            try:
                stream.stop()
            except Exception:
                pass
        for stream in reversed(streams):
            try:
                stream.close()
            except Exception:
                pass
    print("bridge=stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
