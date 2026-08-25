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
