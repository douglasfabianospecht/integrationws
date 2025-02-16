import os
import subprocess
import sys
# comando parar gerar o EXE  
# pyinstaller -F --hidden-import=win32timezone --add-data ".env;./" --icon=icon.ico --name ServiceManager ServiceManager.py

def get_executable_path():
    """Retorna o caminho correto do executável DSLSubscriberService.exe."""
    if getattr(sys, 'frozen', False):  # Detecta se está rodando via PyInstaller
        return os.path.join(os.path.dirname(sys.executable), "DSLSubscriberService.exe")
    return os.path.abspath("DSLSubscriberService.exe")  # Caminho normal quando rodando como script

test_service_path = get_executable_path()

if not os.path.exists(test_service_path):
    print(f"❌ ERRO: Arquivo {test_service_path} não encontrado!")
    sys.exit(1)

def install_service():
    print("🔹 Instalando o serviço...")
    subprocess.run([test_service_path, "install"], check=True)

def start_service():
    print("🔹 Iniciando o serviço...")
    subprocess.run([test_service_path, "start"], check=True)

def stop_service():
    print("🔹 Parando o serviço...")
    subprocess.run([test_service_path, "stop"], check=True)

def remove_service():
    print("🔹 Removendo o serviço...")
    subprocess.run([test_service_path, "remove"], check=True)

while True:
    print("\n==============================")
    print(f"✅ DSLSubscriberService.exe encontrado: {test_service_path}")
    print("Opções disponíveis:")
    print("1 - Instalar Serviço")
    print("2 - Iniciar Serviço")
    print("3 - Parar Serviço")
    print("4 - Remover Serviço")
    print("5 - Sair")
    print("==============================")

    option = input("Escolha uma opção (1-5): ").strip()

    if option == "1":
        install_service()
    elif option == "2":
        start_service()
    elif option == "3":
        stop_service()
    elif option == "4":
        remove_service()
    elif option == "5":
        print("Saindo...")
        break
    else:
        print("❌ Opção inválida! Tente novamente.")
