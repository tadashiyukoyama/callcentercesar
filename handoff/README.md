# Pacote de migração

Este diretório contém o estado solicitado para migrar o CRM para outro computador.

- `crm-state.json`: 203 contatos, andamento do funil, cinco registros de chamadas e um evento histórico.
- `../docs/HANDOFF-NOTEBOOK.md`: contexto técnico completo para o próximo Codex.

O JSON contém contatos comerciais e números telefônicos e foi incluído porque o proprietário solicitou explicitamente que o repositório público carregasse a lista e o andamento. Ele não contém `config.json`, senha, token ou credencial.

Para restaurar em um clone novo localizado em `D:\Discador`:

```powershell
python D:\Discador\tools\restore_crm_state.py
```

Se o banco já contiver contatos e a intenção for substituí-los:

```powershell
python D:\Discador\tools\restore_crm_state.py --replace
```

Para atualizar a exportação a partir do banco local atual:

```powershell
python D:\Discador\tools\export_crm_state.py
```
