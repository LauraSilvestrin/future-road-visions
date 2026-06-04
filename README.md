# Future Road Visions

## Requisitos

Antes de começar, instale:

* Git
* Node.js (versão 20 ou superior)
* Python 3.11 ou superior

---

## 1. Clonar o projeto

Abra o Prompt de Comando ou PowerShell e execute:

```bash
git clone https://github.com/LauraSilvestrin/future-road-visions.git
cd future-road-visions
```

---

## 2. Configurar e executar o Backend

Abra um terminal na pasta do backend:

```bash
cd backend
```

Crie o ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente virtual:

```bash
.venv\Scripts\activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Inicie o backend:

```bash
python main.py
```

Se tudo estiver correto, o backend ficará disponível em:

```text
http://localhost:8000
```

---

## 3. Configurar e executar o Frontend

Abra um novo terminal.

Acesse a pasta do frontend:

```bash
cd frontend
```

Instale as dependências:

```bash
npm install
```

Crie um arquivo chamado `.env.local` na pasta do frontend contendo:

```env
VITE_API_URL=http://localhost:8000
```

Inicie o frontend:

```bash
npm run dev
```

O terminal exibirá um endereço semelhante a:

```text
http://localhost:5173
```

Abra esse endereço no navegador.

---

## Ordem correta para executar

Sempre que for utilizar o sistema:

### Terminal 1 (Backend)

```bash
cd backend
.venv\Scripts\activate
python main.py
```

### Terminal 2 (Frontend)

```bash
cd frontend
npm run dev
```

---

## Problemas comuns

### Erro ao executar `python`

Verifique se o Python está instalado e adicionado ao PATH.

Teste com:

```bash
python --version
```

### Erro ao executar `npm`

Verifique se o Node.js está instalado.

Teste com:

```bash
node --version
npm --version
```

### Tela em branco ou erro de conexão

Confirme que:

* O backend está rodando em `http://localhost:8000`
* O arquivo `.env.local` foi criado corretamente
* O frontend foi reiniciado após criar ou alterar o `.env.local`

### Dependências desatualizadas

No frontend:

```bash
npm install
```

No backend:

```bash
pip install -r requirements.txt
```
