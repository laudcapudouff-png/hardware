"""Monitor de uso do hardware para Windows, com interface em português."""

import os
import json
import subprocess
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
	import psutil  # type: ignore
except ImportError:
	psutil = None


class GerenciadorTarefas:
	def __init__(self, janela):
		self.janela = janela
		self.janela.title("Gerenciador de Tarefas — Desempenho")
		self.janela.geometry("760x460")
		self.janela.minsize(600, 380)

		style = ttk.Style()
		style.theme_use("clam")
		self.style = style
		self.tema_escuro = True
		style.configure("Titulo.TLabel", font=("Segoe UI", 18, "bold"))
		style.configure("Uso.TLabel", font=("Segoe UI", 30))
		style.configure("Treeview", rowheight=36, font=("Segoe UI", 10))

		principal = ttk.Frame(janela, padding=18)
		principal.pack(fill="both", expand=True)
		cabecalho = ttk.Frame(principal)
		cabecalho.pack(fill="x")
		ttk.Label(cabecalho, text="Gerenciador de Tarefas", style="Titulo.TLabel").pack(side="left", anchor="w")
		self.botao_tema = ttk.Button(cabecalho, text="Tema claro", command=self.alternar_tema)
		self.botao_tema.pack(side="right")
		ttk.Label(principal, text="Desempenho", font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 14))

		conteudo = ttk.Frame(principal)
		conteudo.pack(fill="both", expand=True)
		conteudo.columnconfigure(1, weight=1)
		conteudo.rowconfigure(0, weight=1)
		self.recursos = ttk.Treeview(conteudo, columns=("uso",), show="tree headings", selectmode="browse")
		self.recursos.heading("#0", text="Recurso")
		self.recursos.heading("uso", text="Uso")
		self.recursos.column("#0", width=130)
		self.recursos.column("uso", width=65, anchor="e")
		self.recursos.grid(row=0, column=0, sticky="nsw", padx=(0, 20))
		self.itens = {
			"cpu": self.recursos.insert("", "end", text="CPU", values=("--%",)),
			"memoria": self.recursos.insert("", "end", text="Memória", values=("--%",)),
			"gpu": self.recursos.insert("", "end", text="GPU", values=("N/D",)),
			"ethernet": self.recursos.insert("", "end", text="Ethernet", values=("N/D",)),
		}
		self.nomes = {"cpu": "CPU", "memoria": "Memória", "gpu": "GPU", "ethernet": "Ethernet"}
		self.recursos.bind("<<TreeviewSelect>>", self.selecionar_recurso)
		self.recursos.bind("<Button-3>", self.alternar_grafico_com_botao_direito)

		painel = ttk.Frame(conteudo)
		painel.grid(row=0, column=1, sticky="nsew")
		painel.columnconfigure(0, weight=1)
		painel.rowconfigure(2, weight=1)
		self.nome_recurso = ttk.Label(painel, text="CPU", style="Titulo.TLabel")
		self.nome_recurso.grid(row=0, column=0, sticky="w")
		self.grafico_logico = False
		self.porcentagem = ttk.Label(painel, text="--%", style="Uso.TLabel")
		self.porcentagem.grid(row=1, column=0, sticky="w", pady=(12, 8))
		self.detalhes = ttk.Label(painel, text="", font=("Segoe UI", 10), justify="left")
		self.detalhes.grid(row=3, column=0, sticky="w", pady=(0, 10))
		self.grafico = tk.Canvas(painel, height=200, background="white", highlightthickness=1, highlightbackground="#c8c8c8")
		self.grafico.grid(row=2, column=0, sticky="nsew")
		self.rolagem_grafico = ttk.Scrollbar(painel, orient="vertical", command=self.grafico.yview)
		self.grafico.configure(yscrollcommand=self.rolagem_grafico.set)
		self.grafico.bind("<Configure>", lambda _evento: self.desenhar_grafico())
		self.mensagem = ttk.Label(principal, text="", wraplength=700, font=("Segoe UI", 9))
		self.mensagem.pack(anchor="w", pady=(12, 0))
		self.recurso_selecionado = "cpu"
		self.historico = {recurso: [0] * 60 for recurso in self.itens}
		self.historico_logico = []
		self.historico_gpus = {}
		self.metricas_gpus = []
		self.usos = {}
		self._contadores_ethernet = None
		self._trafego_ethernet = None
		self._adaptadores_ethernet = []
		self.aplicar_tema()

		if psutil is None:
			self.mensagem.config(text="Para monitorar o hardware, instale a dependência: pip install psutil")
			ttk.Button(principal, text="Instruções de instalação", command=self.mostrar_instalacao).pack(anchor="w", pady=8)
			return

		self.atualizar_particoes()
		psutil.cpu_percent(interval=None)
		psutil.cpu_percent(interval=None, percpu=True)
		self.recursos.selection_set(self.itens["cpu"])
		self.atualizar()
		self.janela.after(2000, self.atualizar_periodicamente)

	def alternar_tema(self):
		self.tema_escuro = not self.tema_escuro
		self.aplicar_tema()
		self.desenhar_grafico()

	def alternar_grafico(self):
		self.grafico_logico = not self.grafico_logico
		if self.recurso_selecionado == "cpu" and self.grafico_logico:
			self.rolagem_grafico.grid(row=2, column=1, sticky="ns")
		else:
			self.rolagem_grafico.grid_remove()
		self.desenhar_grafico()

	def alternar_grafico_com_botao_direito(self, evento):
		if self.recursos.identify_row(evento.y) != self.itens["cpu"]:
			return
		self.recursos.selection_set(self.itens["cpu"])
		self.selecionar_recurso()
		self.alternar_grafico()

	def aplicar_tema(self):
		if self.tema_escuro:
			fundo, painel, texto = "#171a21", "#222733", "#e6eaf0"
			secundario, linha, destaque = "#aab4c3", "#394252", "#58a6ff"
			self.botao_tema.config(text="Tema claro")
		else:
			fundo, painel, texto = "#f3f5f8", "#ffffff", "#202832"
			secundario, linha, destaque = "#68737d", "#d8dee7", "#0078d4"
		self.janela.configure(background=fundo)
		self.style.configure("TFrame", background=fundo)
		self.style.configure("TLabel", background=fundo, foreground=texto)
		self.style.configure("Titulo.TLabel", background=fundo, foreground=texto)
		self.style.configure("Uso.TLabel", background=fundo, foreground=destaque)
		self.style.configure("Treeview", background=painel, fieldbackground=painel, foreground=texto)
		self.style.map("Treeview", background=[("selected", destaque)], foreground=[("selected", "#ffffff")])
		self.style.configure("Treeview.Heading", background=fundo, foreground=secundario)
		self.style.configure("TButton", background=painel, foreground=texto, padding=(10, 5))
		self.style.map("TButton", background=[("active", destaque)], foreground=[("active", "#ffffff")])
		self.grafico.configure(background=painel, highlightbackground=linha)
		self.cor_grade = linha
		self.cor_secundaria = secundario
		self.cor_grafico = destaque

	@staticmethod
	def mostrar_instalacao():
		messagebox.showinfo("Instalação", "No terminal, execute:\n\npip install psutil")

	def atualizar_periodicamente(self):
		if self.janela.winfo_exists():
			self.atualizar()
			self.janela.after(2000, self.atualizar_periodicamente)

	def atualizar(self):
		if psutil is None:
			return
		try:
			usos_logicos = psutil.cpu_percent(percpu=True)
			while len(self.historico_logico) < len(usos_logicos):
				self.historico_logico.append([0] * 60)
			self.historico_logico = self.historico_logico[:len(usos_logicos)]
			for historico, uso_logico in zip(self.historico_logico, usos_logicos):
				historico.append(uso_logico)
				del historico[:-60]
			self.metricas_gpus = self.obter_metricas_gpus()
			for indice, gpu in enumerate(self.metricas_gpus):
				historico = self.historico_gpus.setdefault(indice, {"uso": [], "memoria": []})
				for chave in historico:
					valor = gpu.get(chave)
					if valor is not None:
						historico[chave].append(valor)
						historico[chave] = historico[chave][-60:]
			usos = {
				"cpu": psutil.cpu_percent(),
				"memoria": psutil.virtual_memory().percent,
				"gpu": (
					sum(gpu["uso"] for gpu in self.metricas_gpus if gpu["uso"] is not None)
					/ sum(gpu["uso"] is not None for gpu in self.metricas_gpus)
					if any(gpu["uso"] is not None for gpu in self.metricas_gpus)
					else self.obter_uso_gpu()
				),
			}
			for recurso, uso in usos.items():
				if uso is None:
					self.recursos.set(self.itens[recurso], "uso", "N/D")
					self.usos.pop(recurso, None)
					continue
				self.recursos.set(self.itens[recurso], "uso", f"{uso:.0f}%")
				self.historico[recurso].append(uso)
				self.historico[recurso] = self.historico[recurso][-60:]
				self.usos[recurso] = uso

			trafego = self.obter_trafego_ethernet()
			if trafego is None:
				self.recursos.set(self.itens["ethernet"], "uso", "N/D")
				self.usos.pop("ethernet", None)
			else:
				recebido, enviado = trafego
				self.recursos.set(self.itens["ethernet"], "uso", f"↓{recebido:.1f} ↑{enviado:.1f} MB/s")
				self.historico["ethernet"].append(recebido + enviado)
				self.historico["ethernet"] = self.historico["ethernet"][-60:]
				self.usos["ethernet"] = recebido + enviado

			self.atualizar_particoes()
			for recurso in self.itens:
				if not recurso.startswith("disco:"):
					continue
				try:
					uso = psutil.disk_usage(recurso[len("disco:"):]).percent
				except (psutil.Error, OSError):
					self.recursos.set(self.itens[recurso], "uso", "N/D")
					self.usos.pop(recurso, None)
					continue
				self.recursos.set(self.itens[recurso], "uso", f"{uso:.0f}%")
				self.historico[recurso].append(uso)
				self.historico[recurso] = self.historico[recurso][-60:]
				self.usos[recurso] = uso

			uso_atual = self.usos.get(self.recurso_selecionado)
			self.porcentagem.config(text=self.texto_uso(self.recurso_selecionado))
			self.atualizar_detalhes()
			self.desenhar_grafico()
			self.mensagem.config(text="GPU NVIDIA via nvidia-smi; armazenamento por volume. Atualização a cada 2 segundos.")
		except (psutil.Error, OSError):
			self.mensagem.config(text="Uso do hardware indisponível")

	def obter_trafego_ethernet(self):
		contadores = psutil.net_io_counters(pernic=True)
		adaptadores = {
			nome: contador for nome, contador in contadores.items()
			if "ethernet" in nome.casefold()
		}
		if not adaptadores:
			self._contadores_ethernet = None
			self._trafego_ethernet = None
			self._adaptadores_ethernet = []
			return None
		self._adaptadores_ethernet = list(adaptadores)
		agora = time.monotonic()
		atual = (
			sum(contador.bytes_recv for contador in adaptadores.values()),
			sum(contador.bytes_sent for contador in adaptadores.values()),
		)
		anterior = self._contadores_ethernet
		self._contadores_ethernet = (atual, agora)
		if anterior is None:
			self._trafego_ethernet = (0.0, 0.0)
			return self._trafego_ethernet
		intervalo = agora - anterior[1]
		if intervalo <= 0:
			return self._trafego_ethernet
		self._trafego_ethernet = tuple(
			max(0, atual[indice] - anterior[0][indice]) / intervalo / (1024 ** 2)
			for indice in range(2)
		)
		return self._trafego_ethernet

	def texto_uso(self, recurso):
		if recurso == "ethernet":
			if self._trafego_ethernet is None:
				return "N/D"
			recebido, enviado = self._trafego_ethernet
			return f"↓ {recebido:.1f} / ↑ {enviado:.1f} MB/s"
		uso = self.usos.get(recurso)
		return f"{uso:.0f}%" if uso is not None else "N/D"

	def atualizar_particoes(self):
		if psutil is None:
			return
		for particao in psutil.disk_partitions(all=False):
			ponto = particao.mountpoint
			if not ponto:
				continue
			try:
				uso_disco = psutil.disk_usage(ponto)
				if uso_disco.total < 10 * 1024 ** 3:
					continue
			except (psutil.Error, OSError):
				continue
			recurso = f"disco:{ponto}"
			if recurso not in self.itens:
				tipo, modelo = self.identificar_tipo_armazenamento(ponto)
				nome = (
					f"Armazenamento ({tipo}) {modelo or particao.device or ponto} "
					f"— {self.formatar_bytes(uso_disco.total)}"
				)
				self.itens[recurso] = self.recursos.insert("", "end", text=nome, values=("N/D",))
				self.nomes[recurso] = nome
				self.historico[recurso] = [0] * 60

	@staticmethod
	def identificar_tipo_armazenamento(ponto):
		letra = ponto[:1]
		if not letra.isalpha():
			return "tipo desconhecido", None
		comando = (
			f"(Get-Partition -DriveLetter '{letra}' -ErrorAction Stop | "
			"Get-Disk -ErrorAction Stop | Select-Object FriendlyName, MediaType | "
			"ConvertTo-Json -Compress)"
		)
		try:
			resultado = subprocess.run(
				["powershell", "-NoProfile", "-Command", comando],
				capture_output=True, text=True, timeout=5, check=True,
			)
			disco = json.loads(resultado.stdout) if resultado.stdout.strip() else {}
			if isinstance(disco, list):
				disco = disco[0] if disco else {}
			tipo = str(disco.get("MediaType", "")).strip().upper()
			modelo = str(disco.get("FriendlyName", "")).strip() or None
			return {"SSD": "SSD", "HDD": "HD", "SCM": "SCM"}.get(tipo, ), modelo
		except (OSError, subprocess.SubprocessError):
			return "tipo desconhecido", None
		except (AttributeError, TypeError, ValueError):
			return "tipo desconhecido", None

	@staticmethod
	def obter_uso_gpu():
		try:
			resultado = subprocess.run(
				["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
				capture_output=True, text=True, timeout=2, check=True,
			)
			valores = [float(linha.strip()) for linha in resultado.stdout.splitlines() if linha.strip()]
			return sum(valores) / len(valores) if valores else None
		except (OSError, subprocess.SubprocessError, ValueError):
			# O contador do Windows também permite consultar GPUs AMD e Intel.
			comando = (
				"(Get-Counter '\\\\GPU Engine(*)\\Utilization Percentage' -ErrorAction Stop)."
				"CounterSamples | Measure-Object -Property CookedValue -Maximum | "
				"Select-Object -ExpandProperty Maximum | ConvertTo-Json -Compress"
			)
			valor = GerenciadorTarefas.consultar_powershell(comando)
			try:
				return max(0.0, min(100.0, float(valor))) if valor is not None else None
			except (TypeError, ValueError):
				return None

	def selecionar_recurso(self, _evento=None):
		selecionado = self.recursos.selection()
		for recurso, item in self.itens.items():
			if selecionado and selecionado[0] == item:
				self.recurso_selecionado = recurso
				if (recurso == "cpu" and self.grafico_logico) or recurso == "gpu":
					self.rolagem_grafico.grid(row=2, column=1, sticky="ns")
				else:
					self.rolagem_grafico.grid_remove()
				self.nome_recurso.config(text=self.nomes[recurso])
				self.porcentagem.config(text=self.texto_uso(recurso))
				self.atualizar_detalhes()
				self.desenhar_grafico()
				break

	@staticmethod
	def formatar_bytes(valor):
		return f"{valor / (1024 ** 3):.1f} GB"

	@staticmethod
	def consultar_powershell(comando):
		try:
			resultado = subprocess.run(
				["powershell", "-NoProfile", "-Command", comando],
				capture_output=True, text=True, timeout=5, check=True,
			)
			return json.loads(resultado.stdout) if resultado.stdout.strip() else None
		except (OSError, subprocess.SubprocessError, ValueError):
			return None

	@classmethod
	def obter_nome_cpu(cls):
		processador = cls.consultar_powershell(
			"Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name | "
			"ConvertTo-Json -Compress"
		)
		return processador.strip() if isinstance(processador, str) and processador.strip() else "N/D"

	@classmethod
	def obter_memorias_ram(cls):
		modulos = cls.consultar_powershell(
			"Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, SMBIOSMemoryType, "
			"Speed, ConfiguredClockSpeed | ConvertTo-Json -Compress"
		)
		if not modulos:
			return "N/D"
		if isinstance(modulos, dict):
			modulos = [modulos]
		tipos = {
			20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4",
			34: "DDR5", 30: "LPDDR4", 35: "LPDDR5",
		}
		linhas = []
		for indice, modulo in enumerate(modulos, 1):
			capacidade = modulo.get("Capacity")
			tipo = tipos.get(modulo.get("SMBIOSMemoryType"), "GT 730")
			frequencia = modulo.get("ConfiguredClockSpeed") or modulo.get("Speed")
			capacidade_texto = GerenciadorTarefas.formatar_bytes(int(capacidade)) if capacidade else "GT 730"
			frequencia_texto = f"{frequencia} MHz" if frequencia else "GT 730"
			linhas.append(f"Módulo {indice}: {capacidade_texto}, {tipo}, {frequencia_texto}")
		return "\n".join(linhas)

	@classmethod
	def obter_detalhes_gpu(cls):
		uso_gpu = cls.obter_uso_gpu()
		uso_gpu_texto = f"{uso_gpu}%" if uso_gpu is not None else "N/D"
		memoria_compartilhada = cls.obter_memoria_gpu_compartilhada()
		compartilhada = (
			cls.formatar_bytes(memoria_compartilhada)
			if memoria_compartilhada is not None else "N/D"
		)
		dedicadas = []
		integradas = []
		try:
			resultado = subprocess.run(
				["nvidia-smi", "--query-gpu=name,memory.total,memory.used,clocks.current.graphics,clocks.current.memory,utilization.gpu",
				 "--format=csv,noheader,nounits"],
				capture_output=True, text=True, timeout=3, check=True,
			)
			for linha in resultado.stdout.splitlines():
				campos = [campo.strip() for campo in linha.split(",")]
				if len(campos) >= 6:
					dedicadas.append(
						f"{campos[0]}\nMemória dedicada: {campos[2]} MB usados / {campos[1]} MB total\n"
						f"Memória compartilhada: {compartilhada}\n"
						f"Frequência da GPU: {campos[3]} MHz  |  Memória: {campos[4]} MHz\n"
						f"Uso da GPU: {campos[5]}%"
					)
		except (OSError, subprocess.SubprocessError):
			pass
		placas = cls.consultar_powershell(
			"Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM "
			"| ConvertTo-Json -Compress"
		)
		if isinstance(placas, dict):
			placas = [placas]
		if placas:
			for placa in placas:
				nome = str(placa.get("Name") or "GPU desconhecida")
				# NVIDIA já aparece com dados mais completos via nvidia-smi.
				if any(nome.casefold() in linha.casefold() for linha in dedicadas):
					continue
				nome_normalizado = nome.casefold()
				integrada = any(marca in nome_normalizado for marca in (
					"intel(r) uhd", "intel uhd", "intel(r) iris", "intel iris",
					"intel(r) hd graphics", "intel hd graphics", "intel(r) graphics",
					"radeon(tm) graphics", "radeon graphics", "radeon vega",
					"vega 3", "vega 8", "vega 10", "vega 11",
				))
				if any(marca in nome_normalizado for marca in (
					"nvidia", "geforce", "gt 730", "quadro", "radeon rx", "radeon pro",
				)):
					integrada = False
				memoria = placa.get("AdapterRAM")
				memoria_texto = cls.formatar_bytes(int(memoria)) if memoria else "N/D"
				linha = (
					f"{nome}\nMemória dedicada total: {memoria_texto}\n"
					f"Memória compartilhada: {compartilhada}\n"
					f"Frequência da GPU: N/D\nUso da GPU: {uso_gpu_texto}"
				)
				(integradas if integrada else dedicadas).append(linha)

		return (
			"GPU dedicada:\n" + ("\n\n".join(dedicadas) or "N/D")
			+ "\n\nGPU integrada:\n" + ("\n\n".join(integradas) or "N/D")
		)

	@staticmethod
	def obter_uso_gpu():
		comando = (
			"(Get-Counter '\\GPU Engine(*)\\Utilization Percentage' -ErrorAction Stop)."
			"CounterSamples | Where-Object { $_.InstanceName -match 'engtype_3D' } | "
			"Measure-Object -Property CookedValue -Sum | "
			"Select-Object -ExpandProperty Sum | ConvertTo-Json -Compress"
		)
		valor = GerenciadorTarefas.consultar_powershell(comando)
		try:
			return min(100, round(float(valor))) if valor is not None else None
		except (TypeError, ValueError):
			return None

	@staticmethod
	def obter_metricas_gpus():
		gpus = []
		try:
			resultado = subprocess.run(
				["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
				 "--format=csv,noheader,nounits"],
				capture_output=True, text=True, timeout=3, check=True,
			)
			for linha in resultado.stdout.splitlines():
				campos = [campo.strip() for campo in linha.split(",")]
				if len(campos) < 4:
					continue
				try:
					uso = float(campos[1])
					memoria = 100 * float(campos[2]) / float(campos[3]) if float(campos[3]) else None
				except ValueError:
					uso, memoria = None, None
				gpus.append({"nome": campos[0], "uso": uso, "memoria": memoria})
		except (OSError, subprocess.SubprocessError):
			pass
		if gpus:
			return gpus
		placas = GerenciadorTarefas.consultar_powershell(
			"Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name | "
			"ConvertTo-Json -Compress"
		)
		if isinstance(placas, str):
			placas = [placas]
		return [{"nome": nome, "uso": None, "memoria": None}
			for nome in (placas or []) if isinstance(nome, str)]

	@staticmethod
	def obter_memoria_gpu_compartilhada():
		comando = (
			"(Get-Counter '\\GPU Adapter Memory(*)\\Shared Usage' -ErrorAction Stop)."
			"CounterSamples | Measure-Object -Property CookedValue -Sum | "
			"Select-Object -ExpandProperty Sum | ConvertTo-Json -Compress"
		)
		valor = GerenciadorTarefas.consultar_powershell(comando)
		try:
			return int(float(valor)) if valor is not None else None
		except (TypeError, ValueError):
			return None

	@staticmethod
	def obter_tecnologias_cpu():
		try:
			import ctypes

			verificar_recurso = ctypes.windll.kernel32.IsProcessorFeaturePresent
			verificar_recurso.argtypes = [ctypes.c_uint]
			verificar_recurso.restype = ctypes.c_bool
			recursos = (
				(3, "MMX"),
				(6, "SSE"),
				(10, "SSE2"),
				(13, "SSE3"),
				(36, "SSSE3"),
				(37, "SSE4.1"),
				(38, "SSE4.2"),
				(39, "AVX"),
				(40, "AVX2"),
				(41, "AVX-512"),
			)
			tecnologias = [
				nome for identificador, nome in recursos
				if verificar_recurso(identificador)
			]
			return ", ".join(tecnologias) if tecnologias else "N/D"
		except (AttributeError, OSError):
			return "N/D"

	def atualizar_detalhes(self):
		if psutil is None:
			return
		if self.recurso_selecionado == "cpu":
			frequencia = psutil.cpu_freq()
			if frequencia:
				frequencia_texto = (
					f"Em uso: {frequencia.current:.0f} MHz  |  "
					f"Mínima: {frequencia.min:.0f} MHz  |  "
					f"Máxima: {frequencia.max:.0f} MHz"
				)
			else:
				frequencia_texto = "Em uso: N/D  |  Mínima: N/D  |  Máxima: N/D"
			texto = (
				f"Processador: {self.obter_nome_cpu()}\n"
				f"Núcleos: {psutil.cpu_count(logical=False) or 'N/D'} físicos / "
				f"{psutil.cpu_count(logical=True) or 'N/D'} lógicos\n"
				f"Frequência: {frequencia_texto}\n"
				f"Tecnologias (instruções): {self.obter_tecnologias_cpu()}"
			)
		elif self.recurso_selecionado == "memoria":
			memoria = psutil.virtual_memory()
			memoria_swap = psutil.swap_memory()
			texto = (
				f"RAM total: {self.formatar_bytes(memoria.total)}  |  "
				f"Em uso: {self.formatar_bytes(memoria.used)}  |  "
				f"Disponível: {self.formatar_bytes(memoria.available)}\n"
				f"Módulos e frequências:\n{self.obter_memorias_ram()}\n"
				f"Memória virtual (swap): {self.formatar_bytes(memoria_swap.used)} usados / "
				f"{self.formatar_bytes(memoria_swap.total)} total"
			)
		elif self.recurso_selecionado.startswith("disco:"):
			try:
				armazenamento = psutil.disk_usage(self.recurso_selecionado[len("disco:"):])
				texto = (
					f"Capacidade total: {self.formatar_bytes(armazenamento.total)}\n"
					f"Em uso: {self.formatar_bytes(armazenamento.used)}  |  "
					f"Disponível: {self.formatar_bytes(armazenamento.free)}"
				)
			except (psutil.Error, OSError):
				texto = "Informações do armazenamento indisponíveis"
		elif self.recurso_selecionado == "gpu":
			texto = self.obter_detalhes_gpu()
		elif self.recurso_selecionado == "ethernet":
			if self._trafego_ethernet is None:
				texto = "Adaptador Ethernet indisponível"
			else:
				recebido, enviado = self._trafego_ethernet
				texto = (
					f"Adaptador(es): {', '.join(self._adaptadores_ethernet)}\n"
					f"Recebimento: {recebido:.2f} MB/s  |  Envio: {enviado:.2f} MB/s"
				)
		else:
			texto = ""
		self.detalhes.config(text=texto)

	def desenhar_grafico(self):
		if not hasattr(self, "grafico"):
			return
		canvas = self.grafico
		canvas.delete("all")
		largura, altura = canvas.winfo_width(), canvas.winfo_height()
		if largura < 30 or altura < 30:
			return
		if self.recurso_selecionado == "ethernet":
			valores = self.historico["ethernet"]
			maximo = max(valores, default=0) or 1
			canvas.configure(scrollregion=(0, 0, largura, altura))
			margem = 28
			for nivel in range(5):
				y = margem + (altura - 2 * margem) * nivel / 4
				rotulo = maximo * (1 - nivel / 4)
				canvas.create_line(margem, y, largura - 8, y, fill=self.cor_grade)
				canvas.create_text(5, y, text=f"{rotulo:.1f}", anchor="w", fill=self.cor_secundaria, font=("Segoe UI", 8))
			canvas.create_text(largura - 8, 10, text="MB/s", anchor="e", fill=self.cor_secundaria, font=("Segoe UI", 8))
			pontos = []
			for indice, valor in enumerate(valores):
				x = margem + indice * (largura - margem - 12) / max(len(valores) - 1, 1)
				y = altura - margem - valor * (altura - 2 * margem) / maximo
				pontos.extend((x, y))
			if len(pontos) >= 4:
				canvas.create_line(*pontos, fill=self.cor_grafico, width=2, smooth=True)
			return
		if self.recurso_selecionado == "gpu":
			gpus = self.metricas_gpus
			altura_item = 286
			canvas.configure(scrollregion=(0, 0, largura, max(altura, len(gpus) * altura_item)))
			for indice, gpu in enumerate(gpus):
				y0 = indice * altura_item
				canvas.create_text(28, y0 + 14, text=gpu["nome"], anchor="w",
					fill=self.cor_secundaria, font=("Segoe UI", 10, "bold"))
				historicos = self.historico_gpus.get(indice, {})
				for grafico_indice, (chave, rotulo) in enumerate((
					("uso", "Uso da GPU (%)"), ("memoria", "Memória dedicada (%)")
				)):
					gy0 = y0 + 26 + grafico_indice * 128
					gy1 = gy0 + 112
					canvas.create_rectangle(24, gy0, largura - 10, gy1, outline=self.cor_grade)
					canvas.create_text(32, gy0 + 12, text=rotulo, anchor="w",
						fill=self.cor_secundaria, font=("Segoe UI", 8))
					valores = historicos.get(chave, [])
					if not valores:
						canvas.create_text(largura - 20, gy0 + 12, text="N/D", anchor="e",
							fill=self.cor_secundaria)
						continue
					canvas.create_text(largura - 20, gy0 + 12, text=f"{valores[-1]:.0f}%",
						anchor="e", fill=self.cor_grafico, font=("Segoe UI", 8, "bold"))
					for nivel in range(1, 4):
						y = gy0 + 24 + (gy1 - gy0 - 32) * nivel / 4
						canvas.create_line(32, y, largura - 18, y, fill=self.cor_grade)
					pontos = []
					for amostra, valor in enumerate(valores):
						x = 32 + amostra * (largura - 50) / max(len(valores) - 1, 1)
						y = gy1 - 8 - max(0, min(100, valor)) * (gy1 - gy0 - 32) / 100
						pontos.extend((x, y))
					if len(pontos) >= 4:
						canvas.create_line(*pontos, fill=self.cor_grafico, width=2, smooth=True)
			return
		if self.recurso_selecionado == "cpu" and self.grafico_logico:
			quantidade = len(self.historico_logico)
			colunas = max(1, largura // 170)
			altura_grafico = 112
			linhas = (quantidade + colunas - 1) // colunas
			canvas.configure(scrollregion=(0, 0, largura, max(altura, linhas * altura_grafico)))
			cores = ("#f85149", "#3fb950", "#d2a8ff", "#ffa657", "#79c0ff", "#ff7b72")
			self.nome_recurso.config(text=f"CPU — {quantidade} processadores lógicos")
			for indice, valores in enumerate(self.historico_logico):
				coluna, linha = indice % colunas, indice // colunas
				largura_item = largura / colunas
				x0, y0 = coluna * largura_item, linha * altura_grafico
				cor = cores[indice % len(cores)]
				uso = valores[-1] if valores else 0
				canvas.create_rectangle(x0 + 4, y0 + 4, x0 + largura_item - 4,
					y0 + altura_grafico - 4, outline=self.cor_grade)
				canvas.create_text(x0 + 10, y0 + 15, text=f"Lógico {indice + 1}",
					anchor="w", fill=self.cor_secundaria, font=("Segoe UI", 9, "bold"))
				canvas.create_text(x0 + largura_item - 10, y0 + 15, text=f"{uso:.0f}%",
					anchor="e", fill=cor, font=("Segoe UI", 9, "bold"))
				gx0, gy0 = x0 + 10, y0 + 28
				gx1, gy1 = x0 + largura_item - 10, y0 + altura_grafico - 14
				canvas.create_line(gx0, gy1, gx1, gy1, fill=self.cor_grade)
				pontos = []
				for amostra, valor in enumerate(valores):
					x = gx0 + amostra * (gx1 - gx0) / max(len(valores) - 1, 1)
					y = gy1 - valor * (gy1 - gy0) / 100
					pontos.extend((x, y))
				if len(pontos) >= 4:
					canvas.create_line(*pontos, fill=cor, width=2, smooth=True)
			return
		canvas.configure(scrollregion=(0, 0, largura, altura))
		margem = 28
		for nivel in range(5):
			y = margem + (altura - 2 * margem) * nivel / 4
			canvas.create_line(margem, y, largura - 8, y, fill=self.cor_grade)
			canvas.create_text(5, y, text=f"{100 - nivel * 25}%", anchor="w", fill=self.cor_secundaria, font=("Segoe UI", 8))
		series = (
			(self.historico_logico,)
			if self.recurso_selecionado == "cpu" and self.grafico_logico
			else ([self.historico[self.recurso_selecionado]],)
		)
		cores = ("#f85149", "#3fb950", "#d2a8ff", "#ffa657", "#79c0ff", "#ff7b72")
		for serie_indice, serie in enumerate(series):
			for valores in serie:
				pontos = []
				for indice, valor in enumerate(valores):
					x = margem + indice * (largura - margem - 12) / max(len(valores) - 1, 1)
					y = altura - margem - valor * (altura - 2 * margem) / 100
					pontos.extend((x, y))
				if len(pontos) >= 4:
					cor = cores[serie_indice % len(cores)] if self.grafico_logico and self.recurso_selecionado == "cpu" else self.cor_grafico
					canvas.create_line(*pontos, fill=cor, width=2, smooth=True)


if __name__ == "__main__":
	app = tk.Tk()
	GerenciadorTarefas(app)
	app.mainloop()
