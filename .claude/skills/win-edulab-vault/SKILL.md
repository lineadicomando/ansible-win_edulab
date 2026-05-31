---
name: win-edulab-vault
description: Use when adding, editing, or troubleshooting Ansible Vault secrets in this project — covers vault file location, password file, naming conventions, and encrypt/decrypt commands
---

# Ansible Vault secret management — win-edulab project

## Conventions

- All YAML files use the **`.yaml`** extension (never `.yml`)
- The vault password is stored in `.ansible-vault-pass.txt` (project root — never commit this file)
- `ansible.cfg` configures it automatically via `vault_password_file = .ansible-vault-pass.txt`
- Secrets belong **always** in `group_vars/all/vault.yaml`, **never** in `vars.yaml`

---

## Vault file location

Each inventory has its own separate vault:

```
inventories/<lab>/group_vars/all/vault.yaml
```

Encrypted file header:
```yaml
$ANSIBLE_VAULT;1.1;AES256
...
```

When decrypted, the file contains:
```yaml
---
ansible_vault_password: "<winrm-and-ssh-password>"
ansible_vault_become_password: "<privilege-escalation-password>"
```

---

## Variable naming convention

| Vault variable | Referenced in vars.yaml as |
|----------------|---------------------------|
| `ansible_vault_password` | `ansible_password` |
| `ansible_vault_become_password` | `ansible_become_password` |

Pattern: vault variables use the `ansible_vault_*` prefix. Variables in `vars.yaml` reference them as `{{ ansible_vault_<name> }}`.

---

## Useful commands

```bash
# View vault contents
ansible-vault view inventories/school/group_vars/all/vault.yaml

# Edit a vault file
ansible-vault edit inventories/school/group_vars/all/vault.yaml

# Encrypt a plaintext vault file
ansible-vault encrypt inventories/<lab>/group_vars/all/vault.yaml

# Temporarily decrypt
ansible-vault decrypt inventories/<lab>/group_vars/all/vault.yaml

# Re-encrypt after manual edit
ansible-vault encrypt inventories/<lab>/group_vars/all/vault.yaml
```

`ansible.cfg` already sets `vault_password_file`, so `--vault-password-file` is not needed.

---

## Adding a secret to an existing inventory

1. Open the vault: `ansible-vault edit inventories/<lab>/group_vars/all/vault.yaml`
2. Add the variable with the `ansible_vault_*` prefix:
   ```yaml
   ansible_vault_new_variable: "secret-value"
   ```
3. Reference it in `group_vars/all/vars.yaml`:
   ```yaml
   variable_used_elsewhere: "{{ ansible_vault_new_variable }}"
   ```

---

## Creating the vault for a new inventory

```bash
# Create an empty encrypted file
ansible-vault create inventories/<lab>/group_vars/all/vault.yaml
```

Minimum content:
```yaml
---
ansible_vault_password: "<password>"
ansible_vault_become_password: "<become-password>"
```

---

## Troubleshooting

| Problem | Likely cause | Solution |
|---------|-------------|---------|
| `Decryption failed` | Wrong password or missing `.ansible-vault-pass.txt` | Check that `.ansible-vault-pass.txt` exists and contains the correct password |
| Empty variable at runtime | `vault.yaml` missing or not encrypted correctly | `ansible-vault view` to inspect the content |
| `vault.yaml` committed in plaintext | File not encrypted before commit | `ansible-vault encrypt <file>` and review `.gitignore` |
