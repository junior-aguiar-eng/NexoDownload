# 💎 YouTube Study Intelligence — Extensão para Google Chrome (Manifest V3)

Extensão oficial desenvolvida com **Padrão Diamante** de Engenharia de Software da Google para transformar sua experiência de estudo no YouTube.

Integra-se nativamente ao player oficial do YouTube através do **Chrome Side Panel**, sincronizando a fala do professor com a transcrição, anotações no **Método Cornell** e busca instantânea de termos jurídicos e acadêmicos.

---

## 🚀 Como Instalar no Google Chrome / Microsoft Edge (15 Segundos)

1. Abra o navegador (**Google Chrome** ou **Microsoft Edge**).
2. Na barra de endereços, digite:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
3. No canto superior direito, ative a chave **"Modo do desenvolvedor"** (ou *"Developer mode"*).
4. Clique no botão **"Carregar sem compactação"** (ou *"Load unpacked"*).
5. Selecione a pasta da extensão:
   `C:\Users\Boni Jr\Desktop\Transcrições YouTube\chrome_extension`
6. **Pronto!** A extensão com ícone de diamante 💎 já estará instalada.

---

## 🎯 Como Usar Durante os Estudos

### Passo 1: Inicie o Motor de Estudos Local
Basta dar **duplo clique** no arquivo executável:
- [`INICIAR_SERVIDOR_ESTUDOS.bat`](file:///c:/Users/Boni%20Jr/Desktop/Transcri%C3%A7%C3%B5es%20YouTube/INICIAR_SERVIDOR_ESTUDOS.bat)
*(Ou execute `python resumidor.py --serve` no terminal).*

*Isso inicializa a API local ultra-leve na porta 8765, permitindo que a extensão transcreva instantaneamente qualquer aula do YouTube com estruturação semântica, Caderno Cornell e resumo com IA.*

### Passo 2: Abra sua Vídeo-Aula no YouTube
1. Vá até o YouTube e abra qualquer aula (ex: uma aula do Mege, Gran, Estratégia, etc.).
2. Clique no ícone da extensão 💎 na barra do Chrome ou abra o **Painel Lateral** do navegador.
3. O painel se abre ao lado do vídeo:
   - **Sincronização em Tempo Real:** Conforme a aula avança, o parágrafo correspondente acende em azul e a tela rola automaticamente (*Auto-scroll*).
   - **Navegação Clicável:** Clique em qualquer trecho do texto e o player do YouTube pula no milissegundo para aquele momento!
   - **Busca Instantânea:** Digite um artigo de lei (ex: *"artigo 85"*) e veja instantaneamente onde o professor citou o tema.
   - **Abas de Estudo:** Alterne entre a **Transcrição Completa**, o **Caderno Cornell** e o **Resumo Executivo**.
   - **Exportação com 1 Clique:** Baixe as anotações prontas em Markdown ou copie a transcrição.

---

## 🏛️ Estrutura da Extensão

```
chrome_extension/
├── manifest.json         # Configuração Manifest V3 com Side Panel API
├── background.js         # Service worker para gestão do Side Panel
├── content.js            # Content script que controla o player nativo do YouTube
├── icons/                # Ícones PNG de alta resolução (16px, 48px, 128px)
└── sidepanel/
    ├── index.html        # Estrutura do painel de estudos
    ├── style.css         # Tema Dark Mode Google Material Slate/Sky
    └── script.js         # Sincronização, busca e conexão com o motor local
```
