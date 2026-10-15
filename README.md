# WalletAgent

> **Autonomous Web3 Wallet Agent with Z3 Formal Policy Verification & RAG Cognitive Reasoning**

WalletAgent is a mathematically verified autonomous trading agent and wallet policy engine designed for EVM networks (Base Sepolia / Ethereum). It bridges the gap between natural language user intent and provably secure on-chain execution by pairing LLM semantic synthesis with deterministic Z3 SMT solver verification, historical market RAG retrieval, and strict invariant policy guards.

---

## 🌟 Key Features

### 1. Dual-Channel Natural Language Policy Compilation
- **Channel A (Deterministic Parser):** Rule-based semantic dependency parser powered by spaCy and custom grammar rules.
- **Channel B (LLM Synthesizer):** Multi-provider LLM support (Groq, Gemini, OpenAI, Anthropic, or local Ollama) for flexible natural language interpretation.
- **Ambiguity Detection & Resolution:** Proactively detects dimensional and semantic ambiguities (such as ambiguous percentages for gas thresholds) and presents structured mathematical interpretations for user selection.

### 2. Formal Verification & Z3 Equivalence Checking
- **Z3 SMT Solver:** Proves mathematical equivalence between the independent parser and the LLM's synthesis.
- **Safety Invariant Enforcing:** Invariants such as balance floors (`balance_after >= floor`), single transaction caps (`trade <= max_trade`), and cumulative daily spend caps (`spent_today + trade <= daily_limit`) are proved formally using first-order logic.
- **Sort & Type Safety:** Enforces strict dimensional types (`USD`, `GWEI`, `TOKEN`, `PERCENT`) to prevent unit confusion bugs.

### 3. Cognitive Agent Reasoning Engine (Fragmented Cognition)
- **Market History RAG:** Retrieves matching historical market regimes (e.g., *Post-Dip Mean Reversion*, *Gas Spike Congestion Panic*, *Overextended Bull Run*) based on real-time gas prices, volatility, and trend conditions.
- **Autonomous Intent Formulation:** Constructs clear trade theses with risk scoring and profitability outlooks.
- **Dry-Run Simulation:** Estimates slippage, calculates post-swap balances, and projects 24-hour value deltas and drawdown risk prior to execution.
- **Dual Gate Precedence:** Even if market conditions appear favorable, trades cannot execute unless Z3 formal invariant gates return `SAT`.

### 4. Autonomous Agent Daemon Runtime
- **Tick-by-Tick Evaluation:** Background monitoring daemon continuously assesses live market conditions against active task triggers.
- **Single-Task Lifecycle:** Enforces a clean single-active-task lifecycle (`RUNNING`, `FINISHED`, `STOPPED`) with human-in-the-loop control (Pause, Dismiss, Manual Override).
- **Audit Ledger:** Every transaction and dry-run decision records an immutable reasoning audit trail with solver status, RAG metrics, and execution hashes.

### 5. Live Market Feeds & Web3 Simulation
- **Coinbase WebSocket:** Real-time tick-by-tick ETH/USD pricing feed.
- **Ethereum / Base Sepolia RPC:** Live gas tracking (Base fee + Priority fee) and network state inspection (Base Sepolia Chain ID: `84532`).
- **Interactive Web Dashboard:** Lightweight, responsive dashboard built with Flask and Vanilla CSS/JS featuring live charts, interactive guard gate testing, and policy discovery.

---

## 🏗️ Architecture

WalletAgent is a single Python process with a Flask dashboard, background market-feed
workers, and one autonomous agent worker. The dashboard and agent share singleton
services for the exchange, policy state, task registry, reasoning engine, and wallet
database.

### System context

```mermaid
flowchart LR
    User[User / Operator]
    Browser[Browser dashboard]
    Main[main.py<br/>startup orchestrator]
    Flask[Flask application<br/>flask/server.py]
    Agent[AutonomousAgent<br/>agent/runtime.py]
    Policy[Verified policy state]
    Exchange[ExchangeService<br/>exchange/service.py]
    Reasoning[ReasoningEngine<br/>reasoning/engine.py]
    Wallet[UserDatabase<br/>user/db.py]
    Tasks[TaskManager<br/>agent/task.py]
    Coinbase[(Coinbase WebSocket)]
    Ethereum[(Ethereum L1 JSON-RPC)]
    History[(market_history.json)]
    Ledger[(wallet_db.json)]
    TaskStore[(agent_tasks.json)]

    User --> Browser
    Browser <-->|HTML, JSON, SSE| Flask
    Main --> Policy
    Main --> Flask
    Flask --> Policy
    Flask --> Agent
    Flask --> Exchange
    Flask --> Wallet
    Agent --> Exchange
    Agent --> Reasoning
    Agent --> Wallet
    Agent --> Tasks
    Exchange --> Coinbase
    Exchange --> Ethereum
    Reasoning --> History
    Wallet --> Ledger
    Tasks --> TaskStore
```

### Application components

```mermaid
flowchart TB
    subgraph Presentation["Presentation and control"]
        Main["main.py"]
        Dashboard["Flask routes and templates<br/>flask/server.py"]
    end

    subgraph PolicyPlane["Policy plane"]
        RuleReader["RuleReader<br/>deterministic parser"]
        LLMReader["LLMReader<br/>untrusted JSON reader"]
        Typecheck["typecheck + resolve<br/>dimensional sorts"]
        Compare["compare<br/>counterexample search"]
        Sanity["sanity<br/>satisfiable / vacuous / redundant"]
        Compile["z3_compile<br/>named constraints"]
        Verified["VerifiedPolicy<br/>hash + readback + on-chain params"]
    end

    subgraph Perception["Market perception"]
        Coinbase["CoinbaseWebSocketClient"]
        Gas["EthereumL1GasOracle"]
        Scenario["MarketScenarioEmitter"]
        Exchange["ExchangeService"]
    end

    subgraph Decision["Autonomous decision plane"]
        Task["TaskManager<br/>single active task"]
        Runtime["AutonomousAgent<br/>1-second loop"]
        RAG["RAGRetriever"]
        Intent["Reasoning LLM<br/>intent and risk chunks"]
        DryRun["RiskSimulator"]
        Gate["Deterministic trigger/invariant gate"]
    end

    subgraph State["Persistent state"]
        Wallet["UserDatabase"]
        WalletFile[("wallet_db.json")]
        TaskFile[("agent_tasks.json")]
        HistoryFile[("market_history.json")]
    end

    Main --> Dashboard
    Dashboard --> RuleReader
    Dashboard --> LLMReader
    RuleReader --> Typecheck
    LLMReader --> Typecheck
    Typecheck --> Compare
    Compare --> Compile
    Compile --> Sanity
    Sanity --> Verified
    Dashboard --> Exchange
    Coinbase --> Exchange
    Gas --> Exchange
    Scenario --> Exchange
    Dashboard --> Task
    Task --> Runtime
    Exchange --> Runtime
    Runtime --> RAG
    RAG --> Intent
    Intent --> DryRun
    DryRun --> Gate
    Gate --> Wallet
    Runtime --> Wallet
    Wallet --> WalletFile
    Task --> TaskFile
    RAG --> HistoryFile
```

---

## 🚀 Quickstart

### Prerequisites
- Python 3.10+ (tested on Python 3.11 - 3.14)
- Git

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/immo2n/WalletAgent.git
cd WalletAgent

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the example environment configuration:

```bash
cp .env.example .env
```

Edit `.env` to configure your preferred LLM provider and network settings:

```dotenv
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=openai/gpt-oss-20b

CHAIN_ID=84532
RPC_URL=https://sepolia.base.org
PORT=5000
```

*(Note: If no API key is provided, the engine automatically falls back to deterministic rule-based evaluation and mock LLM synthesis for testing).*

### 3. Run the Application

```bash
python main.py
```

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🔄 Runtime Flows

### Application startup

```mermaid
sequenceDiagram
    autonumber
    participant CLI as main.py
    participant Policy as Policy verifier
    participant Exchange as ExchangeService
    participant Server as Flask app
    participant Agent as AutonomousAgent
    participant Browser as Browser

    CLI->>Policy: Parse default or --prompt policy
    Policy-->>CLI: VerifiedPolicy or failure status
    CLI->>Server: Load flask/server.py
    Server->>Policy: set_default_policy(prompt)
    Server->>Exchange: Read market and gas snapshot
    Server->>Agent: create_app() starts daemon
    Agent-->>Server: Background monitoring active
    Server-->>Browser: Serve dashboard at host:port
```

### Natural-language policy verification

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant API as Flask /api/verify
    participant Rule as RuleReader
    participant LLM as LLMReader
    participant Types as typecheck / resolve
    participant Z3 as compare + z3_compile
    participant Sanity as sanity
    participant Result as VerifiedPolicy

    User->>API: Submit natural-language policy
    API->>Rule: Read prompt into Policy AST A
    API->>LLM: Read prompt into Policy AST B
    LLM-->>API: Schema-validated, assumed provenance AST
    API->>Types: Type-check both ASTs
    alt Sort mismatch
        Types-->>API: Clarification options
        API-->>User: Ask for unit interpretation
        User-->>API: Select coercion
        API->>Types: Resolve both ASTs
    end
    API->>Z3: Check A and not B
    API->>Z3: Check B and not A
    alt Counterexample found
        Z3-->>LLM: Repair feedback with counterexample
        LLM-->>API: Revised AST B
    else Equivalent
        Z3-->>API: No counterexamples
    end
    API->>Sanity: Check satisfiable, non-vacuous, non-redundant
    Sanity-->>Result: Hash, readback, and on-chain parameters
    Result-->>API: Deploy verified policy state
```

### Continuous autonomous decision loop

```mermaid
stateDiagram-v2
    [*] --> IDLE
    IDLE --> MONITORING: RUNNING task exists
    MONITORING --> MONITORING: Trigger not met\nupdate task check
    MONITORING --> TRIGGER_MET: Trigger satisfied
    TRIGGER_MET --> MONITORING: RAG/dry-run abort
    TRIGGER_MET --> GUARD_BLOCKED: Formal gate UNSAT
    TRIGGER_MET --> EXECUTING: Risk and formal gates pass
    EXECUTING --> FINISHED: Persist swap and audit report
    GUARD_BLOCKED --> MONITORING: Record blocked transaction
    MONITORING --> PAUSED: User pauses agent
    PAUSED --> MONITORING: User resumes agent
    MONITORING --> STOPPED: User stops task
    FINISHED --> [*]
    STOPPED --> [*]
    IDLE --> ERROR: Unhandled step exception
    MONITORING --> ERROR: Unhandled step exception
    ERROR --> MONITORING: Next loop iteration
```

### Trigger-to-execution reasoning pipeline

```mermaid
flowchart LR
    Tick["Market tick<br/>ETH price + gas + scenario"]
    Trigger{"Task trigger<br/>satisfied?"}
    RAG["1. RAG retrieval<br/>match historical regime"]
    Intent["2. Intent generation<br/>trade thesis and amount"]
    Dry["3. Dry-run simulation<br/>slippage, balances, drawdown"]
    Risk{"Risk acceptable?"}
    Gate["4. Formal gate<br/>trigger and invariant checks"]
    SAT{"Gate SAT?"}
    Execute["Persist balances<br/>append confirmed AGENT swap"]
    AbortRisk["Record blocked-by-guard<br/>high-risk decision"]
    Block["Record blocked-by-guard<br/>policy violation"]

    Tick --> Trigger
    Trigger -- "No" --> Tick
    Trigger -- "Yes" --> RAG --> Intent --> Dry --> Risk
    Risk -- "No" --> AbortRisk
    Risk -- "Yes" --> Gate --> SAT
    SAT -- "No" --> Block
    SAT -- "Yes" --> Execute
```

### Market perception and scenario overrides

```mermaid
flowchart LR
    WS["Coinbase ticker WebSocket<br/>ETH-USD"]
    RPC["Ethereum L1 JSON-RPC<br/>feeHistory / gasPrice"]
    WS --> Price["CoinbaseWebSocketClient<br/>price and rolling history"]
    RPC --> Oracle["EthereumL1GasOracle<br/>base fee + priority tip"]
    Price --> Emitter["MarketScenarioEmitter"]
    Oracle --> Emitter
    Emitter --> State["Effective MarketConditions"]
    Scenario{"Scenario mode"}
    Scenario --> Real["REAL_MARKET"]
    Scenario --> GasDip["GAS_DIP<br/>16.5 gwei"]
    Scenario --> EthDip["ETH_DIP<br/>-3.5% ETH price"]
    Scenario --> HighGas["HIGH_GAS<br/>36 gwei"]
    Real --> Emitter
    GasDip --> Emitter
    EthDip --> Emitter
    HighGas --> Emitter
    State --> Service["ExchangeService"]
    Service --> Dashboard["Dashboard APIs / SSE"]
    Service --> Agent["AutonomousAgent"]
```

### Persistence and audit trail

```mermaid
flowchart TB
    UserAction["User wallet edit or task control"]
    MarketAction["Autonomous agent decision"]
    WalletDB["UserDatabase<br/>thread-safe JSON access"]
    TaskDB["TaskManager<br/>single active task"]
    Report["ReasoningReport"]
    WalletFile[("user/data/wallet_db.json")]
    TaskFile[("agent/data/agent_tasks.json")]

    UserAction --> WalletDB
    MarketAction --> Report
    Report --> WalletDB
    MarketAction --> TaskDB
    WalletDB --> WalletFile
    TaskDB --> TaskFile
    WalletFile --> Ledger["Transaction ledger<br/>USER / AGENT actors"]
    Report --> Ledger
```

### Dashboard API surface

```mermaid
flowchart LR
    UI["Browser dashboard"]
    Market["/api/market/live<br/>/api/market/scenario<br/>/api/market/stream"]
    Wallet["/api/user/wallet<br/>/api/user/transactions<br/>/api/user/reset"]
    Reasoning["/api/reasoning/history<br/>/api/user/transaction/:id/reasoning"]
    Agent["/api/agent/status<br/>/api/agent/task<br/>/api/agent/pause<br/>/api/agent/resume"]
    Policy["/api/verify<br/>/api/validate_intent"]
    Services["ExchangeService<br/>UserDatabase<br/>TaskManager<br/>Policy state"]

    UI --> Market
    UI --> Wallet
    UI --> Reasoning
    UI --> Agent
    UI --> Policy
    Market --> Services
    Wallet --> Services
    Reasoning --> Services
    Agent --> Services
    Policy --> Services
```

## 🧪 Running Tests

The test suite covers formal AST verification, dual-reader equivalence, parser mutations, RAG regime matching, and autonomous runtime loops:

```bash
PYTHONPATH=. pytest tests/
```

All 79 unit and integration tests should pass:
```text
============================== 79 passed in 6.12s ==============================
```

---

## 📖 Example Policies & Prompts

| User Prompt | Action Type | Verified Behavior |
|:---|:---|:---|
| `Buy ETH when gas is under 20 gwei, and never let my balance drop below 500 dollars.` | Compound (Trigger + Guard) | Executes swap when gas `<= 20 gwei` while formally proving balance floor `>= $500`. |
| `Never let balance go under 10000.` | Safety Guard Invariant | Pure invariant monitoring; blocks any trade that reduces USDC balance under $10,000. |
| `Don't spend more than 300 dollars in one transaction.` | Transaction Cap | Invariant guard ensuring `trade <= 300` for all autonomous actions. |
| `Buy if gas price is under 5% and do not go under 500 dollars balance.` | Ambiguous Trigger | Prompts user with 4 mathematical reinterpretations (e.g. 5% below 24h moving average). |

---

## 📁 Repository Structure

```
WalletAgent/
├── agent/                  # Autonomous daemon runtime, task models, and single-task registry
├── exchange/               # Market feeds, WebSocket clients, and live price/gas polling
├── flask/                  # Web dashboard templates, static assets, and API routes
├── policy/                 # Z3 formal verification engine, AST definitions, and parsers
│   ├── ast.py              # First-order logic AST expressions
│   ├── typecheck.py        # Dimensional sort and type checking
│   ├── compare.py          # Z3 equivalence and counterexample checker
│   ├── loop.py             # Dual-reader verification orchestration
│   ├── z3_compile.py       # Named Z3 constraints and bounded domain
│   └── readers/            # RuleReader (spaCy) and LLMReader
├── reasoning/              # Fragmented cognitive reasoning pipeline
│   ├── data/               # Historical market regime database
│   ├── rag.py              # Thread-safe market regime RAG retriever
│   ├── dry_run.py          # Slippage, balance, and risk simulation
│   └── engine.py           # Intent, risk, gate, and audit orchestration
├── testing/                # Supported phrase catalog and reference prompts
├── tests/                  # Pytest unit and integration suite
├── user/                   # Persistent wallet database, balance tracking, and ledger
├── main.py                 # Application entrypoint
└── requirements.txt        # Project dependencies
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
