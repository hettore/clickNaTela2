import pyautogui
import time

print("Pressione Ctrl+C para parar o programa.")

try:
    while True:
        # Pega a posição atual do mouse
        x, y = pyautogui.position()
        # Exibe as coordenadas. O \r faz a linha sobrescrever a anterior
        print(f"Coordenadas do Mouse: X = {x}, Y = {y}", end="\r")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nPrograma encerrado.")
