# Handoff completo — CRM, Android, Bluetooth e migração para notebook

Atualizado em 16/08/2026. Este documento foi criado para que outro Codex consiga continuar o trabalho em um notebook sem depender do histórico desta conversa.

## Objetivo

Executar em `D:\Discador` um CRM local com funil e uma fila de chamadas. O CRM controla um Android via ADB para iniciar e encerrar ligações celulares. A próxima etapa é usar o Bluetooth nativo do notebook para transportar o áudio da chamada até o fone e o microfone USB do computador.

Não há túnel, VoIP ou servidor intermediário. A chamada continua sendo uma chamada celular normal do chip do Android.

## Repositório e execução

- Repositório: `https://github.com/tadashiyukoyama/callcentercesar`
- Branch: `main`
- Caminho desejado: `D:\Discador`
- Aplicação: Python padrão, sem framework externo
- URL local: `http://127.0.0.1:8765`
- Entrada: `app.py`
- Inicializador: `run_discador.ps1`
- ADB esperado: `D:\AndroidTools\platform-tools\adb.exe`
- Banco local: `D:\Discador\data\discador.db`

Comandos para um notebook novo:

```powershell
git clone https://github.com/tadashiyukoyama/callcentercesar.git D:\Discador
Set-Location D:\Discador
python D:\Discador\tools\restore_crm_state.py
Copy-Item D:\Discador\config.example.json D:\Discador\config.json
```

Depois de preencher o novo `device_serial` em `config.json`:

```powershell
powershell -ExecutionPolicy Bypass -File D:\Discador\run_discador.ps1
```

## Estado do CRM incluído no GitHub

O arquivo `handoff/crm-state.json` contém a lista e o andamento completos solicitados:

- 203 contatos no total;
- 200 registros da base pública de restaurantes de Jundiaí;
- 3 contatos de teste locais: `Cesar / Bellarte`, `cesaer / bella` e `teste`;
- 200 contatos com telefone e 3 sem telefone;
- 76 com Instagram;
- 80 com CNPJ;
- 84 com cargo ou função do responsável;
- 13 com observações;
- 5 registros locais de chamadas;
- 1 evento histórico importado.

Distribuição atual do funil:

| Etapa | Quantidade |
|---|---:|
| Novo | 148 |
| Tentativa de contato | 33 |
| Perdido | 15 |
| Retorno | 5 |
| Reunião | 2 |

Todos os nomes, telefones, empresas, Instagram, Facebook, CNPJ, razão social, endereço, cidade, categoria, e-mail, site, prioridade, observações, histórico, retorno e estado do funil disponíveis estão no JSON. `config.json`, tokens e senhas não foram exportados.

Para substituir um banco já preenchido no notebook:

```powershell
python D:\Discador\tools\restore_crm_state.py --replace
```

## Funcionalidades confirmadas do aplicativo

- dashboard e contatos;
- funil Kanban com alteração de etapa;
- observações, último contato e data de retorno;
- histórico de ligações;
- importação CSV;
- fila de contatos elegíveis;
- discagem pelo Android com `ACTION_CALL` via ADB;
- desligamento via ADB;
- tentativa de ativar viva-voz por `uiautomator`;
- operação automática assistida, uma ligação por vez;
- parada quando o Android informa que a chamada conectou;
- registro manual como atendeu, interessado, recusou, reunião, caixa postal, número inválido, ocupado, caiu, não atendeu ou retorno.

Limitação intencional: Android informa que a chamada conectou, mas não informa de forma confiável se foi uma pessoa ou caixa postal. Quando há conexão, o CRM para e aguarda classificação humana.

O aplicativo nunca inicia uma chamada apenas por ser aberto. A discagem exige ação nos botões **Ligar**, **Registrar e chamar próximo** ou **Iniciar**.

## Android atual

Dados observados diretamente pelo ADB:

- fabricante: Xiaomi;
- nome exibido: `Redmi 13`;
- modelo: `24040RN64Y`;
- device: `moon`;
- product: `moon_ru`;
- Android 15, API 35;
- nome Bluetooth visto no PC: `Redmi 13cesar`;
- depuração USB e depuração sem fio habilitadas;
- serial ADB usado nesta sessão: `192.168.100.5:42067`.

O IP e principalmente a porta da depuração sem fio podem mudar. No notebook, executar:

```powershell
D:\AndroidTools\platform-tools\adb.exe devices -l
```

Copiar o serial atual para `D:\Discador\config.json`. Nunca tratar `192.168.100.5:42067` como endereço permanente.

O telefone antigo era um `BV5300 Pro`, com metade da tela quebrada. Ele não é mais o alvo principal.

## Separação importante: controle e áudio

ADB e Bluetooth têm papéis diferentes:

```text
CRM no PC --ADB/Wi-Fi--> Android --> inicia/encerra/controla a chamada

fone+microfone USB <--> Windows <--> HFP/SCO Bluetooth <--> Android <--> chamada celular
```

ADB não transporta o áudio telefônico. As opções de codec A2DP no modo desenvolvedor também não controlam o codec de uma chamada HFP. As opções MAP 1.2/1.3/1.4 afetam mensagens, não o áudio da ligação.

## Computador em que o problema foi diagnosticado

- Windows 11 Pro x64, build `26200`;
- Python `3.13.13`;
- nome Bluetooth apresentado ao celular: `CESAR-PC`;
- fone e microfone USB: `USB PnP Sound Device`;
- adaptador atual: `Generic Bluetooth Radio`;
- hardware ID: `USB\VID_0A12&PID_0001`;
- descrição do barramento: `Bluetooth V2.0 Dongle`;
- fabricante vindo do INF: `Cambridge Silicon Radio Ltd.`;
- LMP: Bluetooth 2.0 + EDR;
- MAC: `00:1B:10:00:2A:EC`;
- driver Microsoft `bth.inf`, versão `10.0.26100.8972`;
- transporte SCO: `InBand`, portanto os dados de voz precisam atravessar o próprio USB do dongle;
- `SCO Max Channels = 2` no Registro;
- sem suporte de recuperação FLDR/PLDR reportado;
- ocorreram eventos BTHUSB de evento HCI malformado e timeout de comando após inserir esse adaptador.

O outro adaptador testado não permaneceu funcional no Windows. Não instalar drivers aleatórios de “CSR Harmony” sem identificar com precisão o hardware.

## Endpoints observados no computador antigo

Estes GUIDs são evidência histórica e mudarão no notebook:

| Uso | Nome | Endpoint |
|---|---|---|
| Saída HFP para o celular | Alto-falantes (`Redmi 13cesar Hands-Free HF Audio`) | `{0.0.0.00000000}.{ec580e48-bca6-450e-ace3-0c278054a449}` |
| Entrada HFP vinda do celular | Microfone (`Redmi 13cesar Hands-Free HF Audio`) | `{0.0.1.00000000}.{c138034c-dcea-462f-ad7c-2645ce19a306}` |
| Saída do fone USB | Alto-falantes (`USB PnP Sound Device`) | `{0.0.0.00000000}.{0cb919b3-9d95-47f8-a389-107728e157d8}` |
| Entrada do fone USB | Microfone (`USB PnP Sound Device`) | `{0.0.1.00000000}.{325ca49a-068f-4654-9d1c-6c807f7fb7b3}` |

O Windows guardava a política por aplicativo em:

```text
HKCU\Software\Microsoft\Multimedia\Audio\DefaultEndpoint\34331421_0
```

Mesmo quando o Mixer de Volume voltava a mostrar os dois seletores vazios, a inspeção ao vivo confirmava que as sessões de captura e renderização continuavam em `USB PnP Sound Device`. Era um problema visual da interface para a sessão HFP gerenciada pelo `Audiosrv`, não perda real da seleção.

## Diagnóstico de áudio já realizado

### O que foi comprovado

Durante uma chamada real:

1. O Android registrou `ActiveBluetoothRoute`.
2. O Android registrou `eSCO-CONNECTED ... CESAR-PC status=Success`.
3. A chamada permaneceu ativa durante o teste de áudio.
4. O endpoint HFP do Windows estava ativo, em 100% e sem mute.
5. O formato de mixagem era mono, float32, 16 kHz — caminho de voz larga/mSBC.
6. Um gerador WASAPI nativo gravou 80.000 frames, cinco segundos de 440 Hz a 35%, diretamente no endpoint de renderização HFP.
7. O buffer foi consumido pelo driver/engine: 401 escritas e 801 mudanças de padding.
8. O telefone do outro lado da chamada não reproduziu o apito.
9. Uma captura WASAPI nativa do endpoint HFP ficou oito segundos aberta e recebeu zero pacotes/zero frames.

Conclusão técnica: o controle HFP e a criação do enlace eSCO acontecem, mas não há payload de voz útil em nenhuma direção. O Mixer, o volume, o VB-Cable, o Iriun e o fone USB foram excluídos como causa do teste direto. A falha está depois do endpoint HFP do Windows e antes do áudio chegar ao Android — pilha/driver/transporte SCO do controlador; o dongle USB 2.0 é o principal suspeito.

Não foi feita uma captura ETW/HCI em nível de pacote porque os canais analíticos exigiam elevação. Portanto, “defeito físico no dongle” é a hipótese mais forte, não uma certeza matemática. O notebook com Bluetooth integrado é o teste discriminante correto.

### Serviços relevantes

- `Audiosrv`
- `AudioEndpointBuilder`
- `BTAGService`
- `BthAvctpSvc`
- `bthserv`
- `PhoneExperienceHost` / Vincular ao Celular

O `BTAGService` chegou a ficar em `StopPending` em um reinício anterior; foi encerrado com segurança e reiniciado. Não há serviço Jarvis ativo controlando o áudio.

### Roteamento virtual antigo

Um projeto antigo do Jarvis/Gemini tinha políticas por aplicativo para:

- `CABLE In 16ch (VB-Audio Virtual Cable)`;
- microfone virtual;
- `Microfone (Iriun Webcam)`.

Foram removidas nove políticas antigas de áudio e duas permissões antigas, com backup em:

```text
D:\Tools\SoundVolumeView\legacy-jarvis-cleanup-20260816
```

Os endpoints VB-Cable e o endpoint de microfone do Iriun foram desativados; a câmera Iriun não foi removida. Isso não corrigiu o SCO e confirmou que o cabo virtual não era a causa principal.

## Procedimento recomendado no notebook com Bluetooth nativo

1. Não conectar nenhum dongle Bluetooth USB durante o primeiro teste.
2. Confirmar no Gerenciador de Dispositivos que existe apenas o rádio Bluetooth interno ativo.
3. Instalar o driver Bluetooth oficial do fabricante do notebook, não um pacote genérico de sites de drivers.
4. Remover do Redmi o pareamento antigo `CESAR-PC` se ele atrapalhar.
5. Emparelhar o Redmi diretamente ao notebook.
6. Vincular novamente o Android ao aplicativo **Vincular ao Celular**.
7. Dar ao Link to Windows/Vincular ao Celular permissões de chamadas, contatos, registro de chamadas, microfone e dispositivos próximos.
8. Fazer uma chamada de teste somente pelo Vincular ao Celular, antes de iniciar o CRM.
9. Confirmar áudio nos dois sentidos usando os alto-falantes/microfone do próprio notebook.
10. Só depois selecionar `USB PnP Sound Device` como dispositivo padrão e de comunicações e testar o fone USB.
11. Abrir o Mixer de Volume durante a chamada. Na sessão `Microfone (<Redmi> Hands-Free HF Audio)`, escolher saída e entrada USB. Validar pelo áudio real; não confiar apenas no seletor visual após reabrir a tela.
12. Quando o áudio manual funcionar, iniciar o CRM e testar uma única chamada antes da fila automática.

O Windows pressupõe um único controlador Bluetooth. Evitar rádio interno e dongle ativos ao mesmo tempo durante o diagnóstico.

## Fallback de codec CVSD

O Windows suporta CVSD a 8 kHz e mSBC a 16 kHz para HFP. No computador antigo, o endpoint apareceu em 16 kHz. Foi preparado um teste reversível para retirar o anúncio de negociação de codec e Wide Band Speech, forçando o fallback CVSD.

No computador antigo, os valores eram:

```text
HKLM\SYSTEM\CurrentControlSet\Control\Bluetooth\Audio\Hfp\HandsFree
BrsfSupportedFeatures = 183
SdpSupportedFeatures  = 55
```

O teste preparado faria bit-clear, não substituição cega:

- limpar bit 7 (`0x80`) de `BrsfSupportedFeatures`;
- limpar bit 5 (`0x20`) de `SdpSupportedFeatures`;
- resultado naquele PC: `183 -> 55` e `55 -> 23`.

Essa alteração **não chegou a ser aplicada** no computador antigo porque a elevação/UAC não foi confirmada. No notebook, testar primeiro o codec padrão. Usar apenas como fallback:

```powershell
Start-Process powershell.exe -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File "D:\Discador\tools\windows\force_hfp_cvsd.ps1"'
```

O script exporta backup antes de alterar. Para restaurar:

```powershell
Start-Process powershell.exe -Verb RunAs -ArgumentList '-ExecutionPolicy Bypass -File "D:\Discador\tools\windows\restore_hfp_registry.ps1" -BackupPath "CAMINHO_DO_BACKUP.reg"'
```

## Ponte experimental USB ↔ HFP

`tools/call_audio_bridge.py` é um protótipo, não uma solução confirmada. No PC antigo:

- a captura do microfone USB mostrou sinal, chegando a aproximadamente 23% de pico;
- os callbacks duplex WDM-KS do endpoint HFP não avançaram;
- o caminho de entrada do HFP permaneceu em zero.

Isso é coerente com a falha de transporte SCO. No notebook, só vale testar essa ponte se o áudio HFP básico funcionar primeiro.

Dependências, instaladas somente em D::

```powershell
python -m pip install --target D:\Tools\CallAudioBridge\python-packages -r D:\Discador\tools\requirements-diagnostics.txt
python D:\Discador\tools\call_audio_bridge.py --phone-name "Redmi 13" --usb-name "USB PnP Sound Device"
```

O diretório de pacotes pode ser alterado com `CALL_AUDIO_PACKAGES`.

## Referências técnicas primárias

- Microsoft, formatos de comunicação HFP (CVSD 8 kHz e mSBC 16 kHz): `https://learn.microsoft.com/windows/win32/coreaudio/communications-audio-format-capabilities`
- Microsoft, HFP bypass/SCO: `https://learn.microsoft.com/windows-hardware/drivers/audio/bluetooth-hfp-bypass-audio-streaming`
- Microsoft, teste de transporte SCO USB in-band: `https://learn.microsoft.com/windows-hardware/test/hlk/testref/b1a89b7d-e692-4025-9063-95519b03e16b`
- Bluetooth SIG, Hands-Free Profile: `https://www.bluetooth.com/specifications/specs/hands-free-profile-1-7-2/`
- AOSP, gerenciamento de SCO/HFP: `https://source.android.com/docs/core/audio/sco-audio-mgmt`

## Prompt sugerido para o Codex do notebook

> Clone `https://github.com/tadashiyukoyama/callcentercesar` em `D:\Discador`. Leia integralmente `D:\Discador\docs\HANDOFF-NOTEBOOK.md` antes de alterar qualquer coisa. Restaure `handoff\crm-state.json`, configure o ADB do Redmi 13 e verifique primeiro o áudio de chamadas pelo Bluetooth nativo do notebook, sem dongle USB. Preserve tudo em D:, não publique credenciais e use o teste CVSD apenas se o HFP padrão falhar. Depois valide o CRM em `http://127.0.0.1:8765` com uma única ligação.
