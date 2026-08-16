# Discador — CRM local com Android via ADB

Aplicação local para organizar contatos, funil Kanban, retornos e histórico de ligações. O número é discado pelo celular Android conectado ao ADB; nesta etapa, o áudio permanece no viva-voz e no microfone do próprio celular.

## Executar

1. Confirme que o celular aparece no ADB.
2. Execute `run_discador.ps1` ou rode `python D:\Discador\app.py`.
3. Abra [http://127.0.0.1:8765](http://127.0.0.1:8765).

O banco SQLite é criado em `D:\Discador\data`. O caminho padrão do ADB é `D:\AndroidTools\platform-tools\adb.exe` e pode ser ajustado no arquivo `D:\Discador\config.json` depois que ele for criado. Use `config.example.json` como referência se precisar configurar manualmente.

O banco, os backups e a configuração do celular são locais e não são enviados ao GitHub.

## CSV de importação

Os cabeçalhos aceitos incluem `nome`, `empresa`, `telefone`, `instagram`, `etapa`, `data retorno` e `observações`. Separadores vírgula, ponto e vírgula e tabulação são reconhecidos.

## Base de restaurantes

`import_restaurants.py` combina a lista pública do CRM de restaurantes com o arquivo exportado de andamento. O importador preserva responsável, cargo, etapa, prioridade, observações, histórico, Instagram, Facebook quando existir na fonte, CNPJ, razão social, endereço, cidade, categoria, e-mail, site e datas de retorno.

```powershell
python D:\Discador\import_restaurants.py C:\caminho\crm-restaurantes-andamento.json
```

Leads sem telefone continuam visíveis no funil, mas não entram na fila do discador.

## Fluxo de chamada

- Selecione um contato na fila ou na tela de contatos.
- Clique em **Ligar**; o app usa `ACTION_CALL` via ADB.
- **Ativar viva-voz** tenta localizar o botão da tela da chamada por `uiautomator`.
- Classifique o resultado e escolha **Registrar e chamar próximo** para salvar o histórico e iniciar o próximo contato.
- Em **Agendar retorno**, informe a data antes de registrar.
- Em **Operação automática assistida**, o sistema liga para a fila uma vez por vez, registra falhas reconhecíveis e para quando o Android informa que a chamada conectou.

O Android não informa se quem atendeu foi uma pessoa ou a caixa postal. Ambos aparecem como chamada conectada; nesse ponto o sistema para e aguarda sua classificação.

O discador não faz chamadas durante a inicialização. Uma chamada só começa ao clicar em **Ligar**, **Registrar e chamar próximo** ou **Iniciar** na operação automática.
