"""ABI and contract definitions for PolicyWallet smart contract."""
from __future__ import annotations

POLICY_WALLET_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "_owner", "type": "address"},
            {"internalType": "address", "name": "_initialOperator", "type": "address"}
        ],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "oldPolicyHash", "type": "bytes32"},
            {"indexed": True, "internalType": "bytes32", "name": "newPolicyHash", "type": "bytes32"},
            {"indexed": False, "internalType": "uint256", "name": "timestamp", "type": "uint256"}
        ],
        "name": "PolicyUpdated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "bytes32", "name": "policyHash", "type": "bytes32"},
            {"indexed": True, "internalType": "address", "name": "invalidatedBy", "type": "address"}
        ],
        "name": "PolicyInvalidated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "operator", "type": "address"},
            {"indexed": False, "internalType": "bool", "name": "authorized", "type": "bool"}
        ],
        "name": "OperatorStatusChanged",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": False, "internalType": "bool", "name": "isPaused", "type": "bool"},
            {"indexed": True, "internalType": "address", "name": "triggeredBy", "type": "address"}
        ],
        "name": "EmergencyPauseToggled",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "token", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "spender", "type": "address"}
        ],
        "name": "AllowanceRevoked",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "tokenIn", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "tokenOut", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"indexed": False, "internalType": "uint256", "name": "amountOut", "type": "uint256"},
            {"indexed": False, "internalType": "bytes32", "name": "policyHash", "type": "bytes32"}
        ],
        "name": "SwapExecuted",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "internalType": "address", "name": "token", "type": "address"},
            {"indexed": True, "internalType": "address", "name": "recipient", "type": "address"},
            {"indexed": False, "internalType": "uint256", "name": "amount", "type": "uint256"},
            {"indexed": False, "internalType": "bytes32", "name": "policyHash", "type": "bytes32"}
        ],
        "name": "TransferExecuted",
        "type": "event"
    },
    # Functions
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "activePolicyHash",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "isPaused",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "operator", "type": "address"}],
        "name": "authorizedOperators",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "token", "type": "address"}],
        "name": "isTokenAllowed",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "recipient", "type": "address"}],
        "name": "isRecipientAllowed",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "minBalanceFloorUsd",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "perTxCapUsd",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "dailyCapUsd",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "spentTodayUsd",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "bytes32", "name": "_policyHash", "type": "bytes32"},
            {"internalType": "uint256", "name": "_minBalanceFloorUsd", "type": "uint256"},
            {"internalType": "uint256", "name": "_perTxCapUsd", "type": "uint256"},
            {"internalType": "uint256", "name": "_dailyCapUsd", "type": "uint256"},
            {"internalType": "address[]", "name": "_allowedTokens", "type": "address[]"},
            {"internalType": "address[]", "name": "_allowedRecipients", "type": "address[]"}
        ],
        "name": "setPolicy",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "invalidatePolicy",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "operator", "type": "address"},
            {"internalType": "bool", "name": "authorized", "type": "bool"}
        ],
        "name": "setOperator",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "operator", "type": "address"}],
        "name": "revokeOperator",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"}
        ],
        "name": "revokeAllowance",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "pause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "unpause",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "tokenIn", "type": "address"},
            {"internalType": "address", "name": "tokenOut", "type": "address"},
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "minAmountOut", "type": "uint256"},
            {"internalType": "uint256", "name": "tradeAmountUsd", "type": "uint256"},
            {"internalType": "uint256", "name": "balanceAfterUsd", "type": "uint256"},
            {"internalType": "bytes32", "name": "policyHash", "type": "bytes32"},
            {"internalType": "address", "name": "router", "type": "address"},
            {"internalType": "bytes", "name": "routerData", "type": "bytes"}
        ],
        "name": "executeSwap",
        "outputs": [{"internalType": "uint256", "name": "amountOut", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address payable", "name": "recipient", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {"internalType": "uint256", "name": "transferAmountUsd", "type": "uint256"},
            {"internalType": "uint256", "name": "balanceAfterUsd", "type": "uint256"},
            {"internalType": "bytes32", "name": "policyHash", "type": "bytes32"}
        ],
        "name": "executeTransfer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]
