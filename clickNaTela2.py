import json
from datetime import datetime, timedelta
import ctypes
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from PIL import ImageGrab
import cv2
import numpy as np
import pyautogui
from pynput import mouse


class AplicativoCoordenadas:
    def __init__(self, root):
        self.root = root
        self.root.title("Rastreador e Gravador")
        self.root.geometry("580x740")
        self.root.attributes("-topmost", True)

        self.coordenadas_salvas = []
        self.coordenada_agendamento = None
        self.imagem_agendamento = None
        self.agendamento_ativo = False
        self.ultima_execucao = None
        self._posicao_job = None
        self._agendamento_job = None
        self._captura_windows_job = None
        self.capturando_area = False
        self.ponto_inicial_captura = None
        self.captura_windows_tentativas = 0
        self._clipboard_antes_captura = None
        self.pasta_capturas = os.path.join(os.getcwd(), "capturas")
        os.makedirs(self.pasta_capturas, exist_ok=True)

        self.label_atual = tk.Label(root, text="X: 0 | Y: 0", font=("Arial", 14, "bold"), fg="blue")
        self.label_atual.pack(pady=10)

        lbl_info = tk.Label(root, text="Dê cliques na tela para registrar as posições", font=("Arial", 9, "italic"))
        lbl_info.pack()

        frame_lista = tk.Frame(root)
        frame_lista.pack(pady=15, padx=20, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(frame_lista)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.lista_ui = tk.Listbox(frame_lista, yscrollcommand=scrollbar.set, font=("Arial", 11))
        self.lista_ui.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.lista_ui.yview)
        self.lista_ui.bind("<<ListboxSelect>>", self.selecionar_coordenada)

        # Painel de agendamento automático
        frame_agendamento = tk.LabelFrame(root, text="Agendamento automático")
        frame_agendamento.pack(pady=10, padx=20, fill=tk.X)

        self.dias_var = {}
        dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        for indice, dia in enumerate(dias):
            var = tk.BooleanVar(value=False)
            self.dias_var[dia] = var
            ttk.Checkbutton(frame_agendamento, text=dia, variable=var).grid(row=0, column=indice, sticky="w", padx=3)

        ttk.Label(frame_agendamento, text="Hora:").grid(row=1, column=0, sticky="w", pady=(10, 0), padx=(0, 5))
        self.hora_var = tk.StringVar(value="09:00")
        ttk.Entry(frame_agendamento, textvariable=self.hora_var, width=10).grid(row=1, column=1, sticky="w", pady=(10, 0))

        ttk.Label(frame_agendamento, text="Coordenada:").grid(row=2, column=0, sticky="w", pady=(10, 0), padx=(0, 5))
        self.label_coordenada = tk.StringVar(value="Selecione um ponto")
        ttk.Label(frame_agendamento, textvariable=self.label_coordenada, foreground="darkgreen").grid(row=2, column=1, columnspan=6, sticky="w", pady=(10, 0))

        ttk.Button(frame_agendamento, text="Selecionar imagem", command=self.selecionar_imagem).grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Button(frame_agendamento, text="Capturar da tela", command=self.iniciar_captura_tela).grid(row=3, column=2, sticky="w", pady=(10, 0), padx=(5, 0))

        self.preview_imagem = tk.Label(frame_agendamento, width=12, height=4, bg="white", relief="solid", borderwidth=1)
        self.preview_imagem.grid(row=3, column=3, sticky="w", pady=(10, 0), padx=(5, 0))

        self.label_imagem = tk.StringVar(value="Nenhuma imagem selecionada")
        ttk.Label(frame_agendamento, textvariable=self.label_imagem, foreground="darkorange").grid(row=3, column=4, columnspan=3, sticky="w", pady=(10, 0))

        self.status_agendamento = tk.StringVar(value="Agendamento: desligado")
        ttk.Label(frame_agendamento, textvariable=self.status_agendamento, foreground="navy").grid(row=4, column=0, columnspan=7, sticky="w", pady=(10, 0))

        self.ultimo_clique_var = tk.StringVar(value="Último clique: nunca")
        ttk.Label(frame_agendamento, textvariable=self.ultimo_clique_var, foreground="darkred").grid(row=5, column=0, columnspan=7, sticky="w", pady=(0, 5))

        frame_botoes_agenda = ttk.Frame(frame_agendamento)
        frame_botoes_agenda.grid(row=6, column=0, columnspan=7, pady=(10, 0), sticky="w")

        ttk.Button(frame_botoes_agenda, text="Ativar", command=self.ativar_agendamento).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(frame_botoes_agenda, text="Desativar", command=self.desativar_agendamento).pack(side=tk.LEFT)
        ttk.Button(frame_botoes_agenda, text="Testar agora", command=self.testar_agora).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(frame_botoes_agenda, text="Limpar alvo", command=self.limpar_alvo).pack(side=tk.LEFT, padx=(8, 0))

        frame_botoes = tk.Frame(root)
        frame_botoes.pack(pady=15)

        btn_salvar = ttk.Button(frame_botoes, text="Salvar em JSON", command=self.salvar_json)
        btn_salvar.grid(row=0, column=0, padx=10)

        btn_sair = ttk.Button(frame_botoes, text="Sair", command=self.sair)
        btn_sair.grid(row=0, column=1, padx=10)

        self.atualizar_posicao_atual()

        self.listener = mouse.Listener(on_click=self.ao_clicar)
        self.listener.start()

    def atualizar_posicao_atual(self):
        if not self.root.winfo_exists():
            return

        x, y = pyautogui.position()
        self.label_atual.config(text=f"Mouse Atual -> X: {x} | Y: {y}")
        self._posicao_job = self.root.after(20, self.atualizar_posicao_atual)

    def selecionar_coordenada(self, event=None):
        selecionado = self.lista_ui.curselection()
        if not selecionado:
            return

        indice = selecionado[0]
        if indice >= len(self.coordenadas_salvas):
            return

        ponto = self.coordenadas_salvas[indice]
        self.coordenada_agendamento = (ponto["x"], ponto["y"])
        self.imagem_agendamento = None
        self.label_coordenada.set(f"X={ponto['x']} | Y={ponto['y']}")
        self.label_imagem.set("Nenhuma imagem selecionada")

    def atualizar_preview_imagem(self, caminho):
        try:
            imagem = tk.PhotoImage(file=caminho)
            largura = imagem.width()
            altura = imagem.height()
            maior = max(largura, altura)
            if maior > 120:
                fator = 120 / maior
                nova_largura = max(1, int(largura * fator))
                nova_altura = max(1, int(altura * fator))
                imagem = imagem.subsample(max(1, int(max(largura / nova_largura, altura / nova_altura))), max(1, int(max(largura / nova_largura, altura / nova_altura))))
            self.preview_imagem.configure(image=imagem)
            self.preview_imagem.image = imagem
        except Exception:
            self.preview_imagem.configure(image="")
            self.preview_imagem.image = None

    def selecionar_imagem(self):
        caminho = filedialog.askopenfilename(
            title="Selecione a imagem para o clique",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("Todos os arquivos", "*.*")],
        )
        if not caminho:
            return

        self.imagem_agendamento = caminho
        self.label_imagem.set(caminho)
        self.coordenada_agendamento = None
        self.label_coordenada.set("Selecione um ponto")
        self.atualizar_preview_imagem(caminho)

    def limpar_alvo(self):
        self.coordenada_agendamento = None
        self.imagem_agendamento = None
        self.preview_imagem.configure(image="")
        self.preview_imagem.image = None
        self.label_coordenada.set("Selecione um ponto")
        self.label_imagem.set("Nenhuma imagem selecionada")

    def limpar_clipboard_windows(self):
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            if user32.OpenClipboard(None):
                user32.EmptyClipboard()
                user32.CloseClipboard()
                return True
            return False
        except Exception:
            return False

    def iniciar_captura_tela(self):
        if os.name != "nt":
            messagebox.showwarning("Windows necessário", "Esse recurso usa a captura nativa do Windows (Win + Shift + S).")
            return

        self.capturando_area = False
        self.ponto_inicial_captura = None
        self.captura_windows_tentativas = 0
        self._clipboard_antes_captura = None
        try:
            self._clipboard_antes_captura = ImageGrab.grabclipboard()
        except Exception:
            self._clipboard_antes_captura = None

        self.limpar_clipboard_windows()
        self.label_imagem.set("Escurecendo a tela para selecionar...")
        messagebox.showinfo("Captura do Windows", "A tela vai escurecer. Selecione a área desejada com o mouse.")

        try:
            pyautogui.hotkey("win", "shift", "s")
        except Exception:
            messagebox.showwarning("Captura indisponível", "Não foi possível abrir o atalho de captura do Windows.")
            return

        if self._captura_windows_job is not None:
            self.root.after_cancel(self._captura_windows_job)

        self._captura_windows_job = self.root.after(300, self.verificar_clipboard_captura)

    def verificar_clipboard_captura(self):
        self.captura_windows_tentativas += 1

        try:
            imagem = ImageGrab.grabclipboard()
        except Exception:
            imagem = None

        if imagem is not None:
            if self._clipboard_antes_captura is not None:
                try:
                    if np.array_equal(np.array(self._clipboard_antes_captura), np.array(imagem)):
                        if self.captura_windows_tentativas < 200:
                            self._captura_windows_job = self.root.after(250, self.verificar_clipboard_captura)
                            return
                except Exception:
                    pass

            caminho = os.path.join(self.pasta_capturas, f"alvo_agendamento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            imagem.save(caminho)
            self.imagem_agendamento = caminho
            self.coordenada_agendamento = None
            self.label_imagem.set(caminho)
            self.label_coordenada.set("Selecione um ponto")
            messagebox.showinfo("Imagem salva", f"Imagem salva em:\n{caminho}")
            self._captura_windows_job = None
            return

        if self.captura_windows_tentativas < 200:
            self._captura_windows_job = self.root.after(250, self.verificar_clipboard_captura)
            return

        self.label_imagem.set("Nenhuma imagem capturada")
        self._captura_windows_job = None
        messagebox.showwarning("Tempo esgotado", "A seleção não foi concluída no tempo esperado.")

    def salvar_imagem_cortada(self, x1, y1, x2, y2):
        if x1 == x2 or y1 == y2:
            messagebox.showwarning("Área inválida", "Selecione uma região maior para recortar.")
            return

        esquerda = min(x1, x2)
        topo = min(y1, y2)
        direita = max(x1, x2)
        fundo = max(y1, y2)

        screenshot = pyautogui.screenshot(region=(esquerda, topo, direita - esquerda, fundo - topo))
        caminho = os.path.join(self.pasta_capturas, f"alvo_agendamento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        screenshot.save(caminho)

        self.imagem_agendamento = caminho
        self.coordenada_agendamento = None
        self.label_imagem.set(caminho)
        self.label_coordenada.set("Selecione um ponto")
        self.atualizar_preview_imagem(caminho)
        messagebox.showinfo("Imagem salva", f"Imagem salva em:\n{caminho}")

    def ao_clicar(self, x, y, button, pressed):
        if self.capturando_area:
            if pressed and button == mouse.Button.left:
                wx = self.root.winfo_rootx()
                wy = self.root.winfo_rooty()
                ww = self.root.winfo_width()
                wh = self.root.winfo_height()

                if wx <= x <= wx + ww and wy <= y <= wy + wh:
                    return

                if self.ponto_inicial_captura is None:
                    self.ponto_inicial_captura = (x, y)
                    self.label_imagem.set("Agora clique no canto inferior direito...")
                else:
                    self.capturando_area = False
                    self.salvar_imagem_cortada(self.ponto_inicial_captura[0], self.ponto_inicial_captura[1], x, y)
            return

        if pressed and button == mouse.Button.left:
            wx = self.root.winfo_rootx()
            wy = self.root.winfo_rooty()
            ww = self.root.winfo_width()
            wh = self.root.winfo_height()

            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                return

            ponto = {"x": x, "y": y}
            self.coordenadas_salvas.append(ponto)

            self.root.after(0, lambda: self.lista_ui.insert(tk.END, f"Clique {len(self.coordenadas_salvas)}: X={x}, Y={y}"))
            self.root.after(0, lambda: self.lista_ui.selection_clear(0, tk.END))
            self.root.after(0, lambda: self.lista_ui.selection_set(tk.END))
            self.root.after(0, lambda: self.selecionar_coordenada())

    def ativar_agendamento(self):
        if self.coordenada_agendamento is None and self.imagem_agendamento is None:
            messagebox.showwarning("Seleção obrigatória", "Selecione uma coordenada ou uma imagem antes de ativar o agendamento.")
            return

        dias_selecionados = [dia for dia, variavel in self.dias_var.items() if variavel.get()]
        if not dias_selecionados:
            messagebox.showwarning("Seleção obrigatória", "Escolha pelo menos um dia da semana para o agendamento.")
            return

        try:
            datetime.strptime(self.hora_var.get(), "%H:%M")
        except ValueError:
            messagebox.showwarning("Formato inválido", "Informe a hora no formato HH:MM, por exemplo 09:30.")
            return

        self.agendamento_ativo = True
        self.ultima_execucao = None

        if self.coordenada_agendamento is not None:
            x, y = self.coordenada_agendamento
            alvo_texto = f"coordenada X={x}, Y={y}"
        elif self.imagem_agendamento:
            alvo_texto = "imagem"
        else:
            alvo_texto = "alvo"

        self.status_agendamento.set(f"Agendamento: ativo para {', '.join(dias_selecionados)} às {self.hora_var.get()} ({alvo_texto})")
        if self._agendamento_job is not None:
            self.root.after_cancel(self._agendamento_job)
        self._agendamento_job = self.root.after(1000, self.verificar_agendamento)

    def testar_agora(self):
        if self.coordenada_agendamento is None and self.imagem_agendamento is None:
            messagebox.showwarning("Seleção obrigatória", "Selecione uma coordenada ou uma imagem antes de testar.")
            return

        self.executar_click_agendado()
        self.ultimo_clique_var.set(f"Último clique: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        self.status_agendamento.set("Teste manual executado")

    def desativar_agendamento(self):
        self.agendamento_ativo = False
        if self._agendamento_job is not None:
            self.root.after_cancel(self._agendamento_job)
            self._agendamento_job = None
        self.status_agendamento.set("Agendamento: desligado")

    def verificar_agendamento(self):
        if not self.agendamento_ativo:
            return

        agora = datetime.now()
        dia_atual = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][agora.weekday()]

        if not self.dias_var.get(dia_atual, tk.BooleanVar(value=False)).get():
            self._agendamento_job = self.root.after(1000, self.verificar_agendamento)
            return

        hora_atual = agora.strftime("%H:%M")
        if hora_atual != self.hora_var.get():
            self._agendamento_job = self.root.after(1000, self.verificar_agendamento)
            return

        if self.ultima_execucao is not None and agora - self.ultima_execucao < timedelta(minutes=1):
            self._agendamento_job = self.root.after(1000, self.verificar_agendamento)
            return

        self.executar_click_agendado()
        self.ultima_execucao = agora
        self._agendamento_job = self.root.after(1000, self.verificar_agendamento)

    def carregar_template_imagem(self):
        if not self.imagem_agendamento:
            return None

        caminho = os.path.abspath(self.imagem_agendamento)
        print(f"Tentando carregar imagem: {caminho}")

        if not os.path.exists(caminho):
            print(f"Arquivo não encontrado: {caminho}")
            return None

        try:
            from PIL import Image
            imagem = Image.open(caminho).convert("RGB")
            array = np.array(imagem)
            return cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
        except Exception as erro:
            print(f"Erro ao abrir a imagem via PIL: {erro}")
            return None

    def executar_click_agendado(self):
        if self.imagem_agendamento:
            try:
                template = self.carregar_template_imagem()
                if template is None:
                    print(f"Não foi possível ler a imagem: {self.imagem_agendamento}")
                    return

                screenshot = np.array(pyautogui.screenshot())
                screenshot_bgr = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
                resultado = cv2.matchTemplate(screenshot_bgr, template, cv2.TM_CCOEFF_NORMED)
                _, valor_maximo, _, posicao = cv2.minMaxLoc(resultado)

                if valor_maximo < 0.7:
                    print(f"Imagem não encontrada: {self.imagem_agendamento} (score={valor_maximo})")
                    return

                h, w = template.shape[:2]
                centro_x = posicao[0] + w // 2
                centro_y = posicao[1] + h // 2
                pyautogui.moveTo(centro_x, centro_y, duration=0.2)
                pyautogui.click(centro_x, centro_y)
                print(f"Clique realizado na imagem: {self.imagem_agendamento} com score={valor_maximo}")
                self.ultimo_clique_var.set(f"Último clique: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                return
            except Exception as erro:
                print(f"Erro ao localizar imagem: {erro}")
                return

        if self.coordenada_agendamento is None:
            return

        x, y = self.coordenada_agendamento
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click(x, y)
        self.ultimo_clique_var.set(f"Último clique: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    def salvar_json(self):
        nome_arquivo = "coordenadas.json"
        with open(nome_arquivo, "w", encoding="utf-8") as f:
            json.dump(self.coordenadas_salvas, f, indent=4)
        print(f"Dados gravados com sucesso em {nome_arquivo}!")

    def sair(self):
        self.agendamento_ativo = False
        if self._posicao_job is not None:
            self.root.after_cancel(self._posicao_job)
        if self._agendamento_job is not None:
            self.root.after_cancel(self._agendamento_job)
        self.listener.stop()
        self.root.destroy()


if __name__ == "__main__":
    janela_principal = tk.Tk()
    app = AplicativoCoordenadas(janela_principal)
    janela_principal.protocol("WM_DELETE_WINDOW", app.sair)
    janela_principal.mainloop()
