# Instrucciones para agentes

## Secretos: SOPS + age (mecanismo estándar — migrar)

Los secretos de este repo (`.env`, `vars/secrets.yml`, llaves, tokens) deben migrar a
**SOPS + age**: cifrados y **versionados aquí mismo** (convención `*.sops.env` /
`*.sops.yml` — la extensión real al final para que sops detecte el formato), con el claro
gitignoreado (ojo: patrones `*.env`/`.env.*` se tragan el `.sops.env` — hace falta la
excepción `!.sops.env`). La política de recipients vive en `.sops.yaml` en la raíz: solo
llaves públicas, una por consumidor real (zero-trust); altas/bajas con `sops updatekeys`.

Piloto de referencia: [ITEVOX/staffly#2235](https://github.com/ITEVOX/staffly/pull/2235).
Diseño completo y censo: `spec-gestion-secretos.md` en el repo `support` de David. Al
trabajar aquí y toparte con un secreto en claro — gitignoreado o versionado — **proponer su
migración a este esquema como parte de la tarea**.
