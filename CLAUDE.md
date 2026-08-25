# icinga-mail-notifications

## Secretos: qué va a SOPS y qué va a Bitwarden (criterio de David, 2026-08-25)

**No es "todo secreto a SOPS."** Dos preguntas, en orden:

1. **¿Quién lo consume?** Una **herramienta** que renderiza un archivo de este repo (Ansible,
   Terraform, `docker compose`, Helm) → **SOPS + age**, cifrado y versionado aquí mismo. Una
   **persona** — entrar a un panel, pasárselo a un tercero, un `curl` ad-hoc → **Bitwarden**,
   un item.
2. **¿Quién lo generó?** Lo generó el despliegue y **nadie lo teclea nunca**
   (`SECRET_KEY_BASE`, un DES key, un blowfish secret) → **SOPS siempre**: un valor que
   ninguna persona escribe no tiene nada que hacer en un gestor de contraseñas. Lo eligió una
   persona o lo emitió un tercero (password de root, login de panel, API key de proveedor) →
   **nunca es sólo-SOPS**.

**Desempate — si aplican las dos, Bitwarden es la fuente de verdad.** Que un password sirva
*además* como variable de un compose o de un `values.yaml` no lo vuelve "secreto de
despliegue": sigue siendo el login de una persona. El uso incidental no cambia el bucket. Si
un consumidor desatendido obliga a copiar ese valor a SOPS, la copia va marcada
(`# espejo de Bitwarden: <item>`) y **se rota desde el origen, nunca editando la copia**.

**Tercer bucket:** lo que consume GitHub Actions (`SOPS_AGE_KEY`, `DOCKERHUB_TOKEN`, tokens
de despliegue) vive en **GitHub Secrets**, con Bitwarden como custodia de la copia
recuperable — no en el SOPS del repo, porque el runner los necesita *antes* de poder
descifrar nada.

**Antipatrón, en las dos direcciones:** no trocear UN archivo de despliegue en varios items
de Bitwarden (deja de ser un artefacto reproducible); no meter credenciales atómicas sueltas
dentro del mismo vault SOPS que las variables de un despliegue.

Criterio completo, con el caso real que lo motivó:
[`spec-gestion-secretos.md` §Capa 0](https://github.com/dferraes/support/blob/main/spec-gestion-secretos.md).

## Secretos: descifrar sin llave local (`SOPS_AGE_KEY_CMD` + Bitwarden)

En máquinas o sesiones que **no** tienen `~/.config/sops/age/keys.txt` — dev containers,
remotos, sesiones de agente — el descifrado de los `*.sops.*` corre vía Bitwarden, sin copiar
la llave a mano a cada máquina nueva:

```sh
export SOPS_AGE_KEY_CMD='rbw get "Llave age personal"'
```

Va en el shell profile de esa máquina (`~/.zshrc`/`~/.bashrc`) o en el `.envrc` del repo si usa
`direnv`. **No toca `.sops.yaml` ni ningún archivo versionado** — es puramente del lado de quien
descifra, no cambia quiénes son recipients. Es **aditivo**: donde ya existe la llave local, ésa
sigue funcionando.

- **No propongas copiar `keys.txt` a mano** — eso es lo que este mecanismo vino a eliminar.
- **No crees un item nuevo de Bitwarden** para la llave: ya existe, se llama
  `Llave age personal`. Dos items con el mismo secreto son dos fuentes de verdad.
- Aplica **sólo a la llave personal de David**. Las llaves generadas en un host y que nunca
  salen de ahí (p. ej. la de un poller de monitoreo) **no se migran** — si el repo tiene más de
  un recipient, verifica cuál es cuál antes de tocar nada.
- **Ojo con el falso OK al verificar:** `sops` cae de vuelta al archivo local sin avisar cuando
  el CMD falla, así que un `sops -d` exitoso en la máquina de David **no prueba** que el CMD
  sirva. La prueba válida esconde el archivo apuntando `XDG_CONFIG_HOME` a un directorio sin
  `sops/age/` — ver el spec.
- El agente **nunca** corre `rbw unlock` ni imprime la línea `AGE-SECRET-KEY-1…`.
  `SOPS_AGE_KEY_CMD` y el nombre del item sí se commitean en claro: son configuración.

Detalle completo y procedimiento de verificación:
[`spec-gestion-secretos.md` §Capa 1](https://github.com/dferraes/support/blob/main/spec-gestion-secretos.md).

