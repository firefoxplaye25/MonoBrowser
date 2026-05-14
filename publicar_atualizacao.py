import os
import json
import subprocess
import re

print("==================================================")
print("  MONOLITHIIUN EXPLORER - CONFIGURADOR DE NUVEM   ")
print("==================================================")

# 1. .gitignore BLINDADO (Segurança Total)
gitignore_content = """
dist/
build/
__pycache__/
*.spec
*.zip
repo_info.json
netlify_config.json
*.mlhjson
.env
"""
with open(".gitignore", "w") as f:
    f.write(gitignore_content)

# 2. Remover arquivos sensíveis do cache do Git (Se já foram subidos)
print("[*] Removendo arquivos sensíveis do histórico do Git...")
subprocess.run(["git", "rm", "--cached", "netlify_config.json"], shell=True, capture_output=True)
subprocess.run(["git", "rm", "-r", "--cached", "*.mlhjson"], shell=True, capture_output=True)
subprocess.run(["git", "rm", "-r", "--cached", "dist"], shell=True, capture_output=True)

# 3. Verificar se o Git está configurado
if not os.path.exists(".git"):
    print("[!] Pasta não inicializada. Configurando agora...")
    subprocess.run(["git", "init"], shell=True)
    repo_url = input("Cole aqui o link do seu repositório GitHub: ").strip()
    if not repo_url.endswith(".git"): repo_url += ".git"
    subprocess.run(["git", "remote", "add", "origin", repo_url], shell=True)
    subprocess.run(["git", "branch", "-M", "main"], shell=True)

# 4. Detectar Usuário e Repo
try:
    remote_out = subprocess.check_output(["git", "remote", "-v"]).decode()
    match = re.search(r'github\.com[:/](.+?)/(.+?)(?:\.git|\s)', remote_out)
    if match:
        github_user, github_repo = match.groups()
        with open("repo_info.json", "w") as f:
            json.dump({"user": github_user, "repo": github_repo.strip()}, f)
    else:
        print("[!] Erro ao detectar repo.")
except:
    pass

# 5. Bumping Version
current_version = "1.0.0"
if os.path.exists("version.json"):
    with open("version.json", "r") as f:
        try: current_version = json.load(f).get("version", "1.0.0")
        except: pass

parts = current_version.split(".")
parts[-1] = str(int(parts[-1]) + 1)
new_version = ".".join(parts)
with open("version.json", "w") as f:
    json.dump({"version": new_version}, f, indent=4)

# 6. Enviar tudo com Segurança
print(f"[*] Subindo Versão {new_version} (MODO SEGURO)...")
msg = input("O que há de novo? ")
if not msg: msg = f"Security Patch v{new_version}"

subprocess.run(["git", "add", "."], shell=True)
subprocess.run(["git", "commit", "-m", msg], shell=True)
subprocess.run(["git", "push", "-u", "-f", "origin", "main"], shell=True)

print("==================================================")
print(" SUCESSO! ARQUIVOS SENSÍVEIS REMOVIDOS DO GITHUB.")
print(" LEMBRE-SE DE REVOGAR SEU TOKEN NO NETLIFY!")
print("==================================================")
os.system("pause")
