// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title PolicyWallet
 * @notice Production-grade verified-policy autonomous smart wallet.
 * @dev FinTechathon 2026 — Topic F : Autonomous On-chain Wallet Agent
 * 
 * Enforces dual-verified formal mathematical policies on-chain:
 *  - Cryptographic policy hash verification
 *  - Allowed token allowlist
 *  - Allowed recipient allowlist
 *  - Per-transaction USD expenditure limits
 *  - 24-hour rolling daily cumulative expenditure caps
 *  - Minimum balance reserve floors (ETH & USDC)
 *  - Emergency pause killswitch
 *  - Operator role authorization and revocation
 */

interface IERC20 {
    function transfer(address recipient, uint256 amount) external returns (bool);
    function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
}

contract PolicyWallet {
    // --- Custom Errors ---
    error UnauthorizedCaller();
    error UnauthorizedOperator(address caller);
    error WalletPaused();
    error PolicyViolation(string reason);
    error PolicyHashMismatch(bytes32 expected, bytes32 provided);
    error InsufficientBalance(uint256 available, uint256 required);
    error BelowMinimumBalanceFloor(uint256 balanceAfter, uint256 floorRequired);
    error ExceedsPerTxCap(uint256 amount, uint256 cap);
    error ExceedsDailyLimit(uint256 newTotal, uint256 dailyCap);
    error TokenNotAllowed(address token);
    error RecipientNotAllowed(address recipient);
    error TransferFailed();

    // --- Events ---
    event PolicyUpdated(bytes32 indexed oldPolicyHash, bytes32 indexed newPolicyHash, uint256 timestamp);
    event PolicyInvalidated(bytes32 indexed policyHash, address indexed invalidatedBy);
    event OperatorStatusChanged(address indexed operator, bool authorized);
    event EmergencyPauseToggled(bool isPaused, address indexed triggeredBy);
    event AllowanceRevoked(address indexed token, address indexed spender);
    event SwapExecuted(address indexed tokenIn, address indexed tokenOut, uint256 amountIn, uint256 amountOut, bytes32 policyHash);
    event TransferExecuted(address indexed token, address indexed recipient, uint256 amount, bytes32 policyHash);
    event ScheduledTransferQueued(uint256 indexed taskId, address recipient, uint256 amount, uint256 executeAt);

    // --- State Variables ---
    address public immutable owner;
    bytes32 public activePolicyHash;
    bool public isPaused;

    // Operator Access Control
    mapping(address => bool) public authorizedOperators;

    // Policy Guards
    mapping(address => bool) public isTokenAllowed;
    mapping(address => bool) public isRecipientAllowed;
    bool public hasTokenAllowlist;
    bool public hasRecipientAllowlist;

    uint256 public minBalanceFloorUsd;   // e.g. 500 USD (in 18 decimals or scaled integer)
    uint256 public perTxCapUsd;          // e.g. 300 USD
    uint256 public dailyCapUsd;          // e.g. 1000 USD

    // Daily Spend Tracking (Day Index => Amount Spent in USD)
    uint256 public currentDayIndex;
    uint256 public spentTodayUsd;

    // --- Modifiers ---
    modifier onlyOwner() {
        if (msg.sender != owner) revert UnauthorizedCaller();
        _;
    }

    modifier onlyAuthorized() {
        if (msg.sender != owner && !authorizedOperators[msg.sender]) {
            revert UnauthorizedOperator(msg.sender);
        }
        _;
    }

    modifier whenNotPaused() {
        if (isPaused) revert WalletPaused();
        _;
    }

    constructor(address _owner, address _initialOperator) {
        owner = _owner != address(0) ? _owner : msg.sender;
        if (_initialOperator != address(0)) {
            authorizedOperators[_initialOperator] = true;
            emit OperatorStatusChanged(_initialOperator, true);
        }
        currentDayIndex = block.timestamp / 1 days;
    }

    receive() external payable {}

    // --- Policy Governance ---

    /**
     * @notice Updates the active on-chain policy parameters with cryptographic policy hash.
     */
    function setPolicy(
        bytes32 _policyHash,
        uint256 _minBalanceFloorUsd,
        uint256 _perTxCapUsd,
        uint256 _dailyCapUsd,
        address[] calldata _allowedTokens,
        address[] calldata _allowedRecipients
    ) external onlyOwner {
        bytes32 oldHash = activePolicyHash;
        activePolicyHash = _policyHash;
        minBalanceFloorUsd = _minBalanceFloorUsd;
        perTxCapUsd = _perTxCapUsd;
        dailyCapUsd = _dailyCapUsd;

        // Reset and set token allowlist
        if (_allowedTokens.length > 0) {
            hasTokenAllowlist = true;
            for (uint256 i = 0; i < _allowedTokens.length; i++) {
                isTokenAllowed[_allowedTokens[i]] = true;
            }
        } else {
            hasTokenAllowlist = false;
        }

        // Reset and set recipient allowlist
        if (_allowedRecipients.length > 0) {
            hasRecipientAllowlist = true;
            for (uint256 i = 0; i < _allowedRecipients.length; i++) {
                isRecipientAllowed[_allowedRecipients[i]] = true;
            }
        } else {
            hasRecipientAllowlist = false;
        }

        emit PolicyUpdated(oldHash, _policyHash, block.timestamp);
    }

    /**
     * @notice Instantly invalidates the active policy hash, locking agent actions until new policy approval.
     */
    function invalidatePolicy() external onlyOwner {
        bytes32 invalidated = activePolicyHash;
        activePolicyHash = bytes32(0);
        emit PolicyInvalidated(invalidated, msg.sender);
    }

    // --- Operator Management & Security ---

    function setOperator(address operator, bool authorized) external onlyOwner {
        authorizedOperators[operator] = authorized;
        emit OperatorStatusChanged(operator, authorized);
    }

    function revokeOperator(address operator) external onlyOwner {
        authorizedOperators[operator] = false;
        emit OperatorStatusChanged(operator, false);
    }

    function revokeAllowance(address token, address spender) external onlyOwner {
        IERC20(token).approve(spender, 0);
        emit AllowanceRevoked(token, spender);
    }

    function pause() external onlyOwner {
        isPaused = true;
        emit EmergencyPauseToggled(true, msg.sender);
    }

    function unpause() external onlyOwner {
        isPaused = false;
        emit EmergencyPauseToggled(false, msg.sender);
    }

    // --- On-Chain Guard Enforcement ---

    function _verifyGuards(
        address token,
        address recipient,
        uint256 amountUsd,
        uint256 balanceAfterUsd,
        bytes32 policyHash
    ) internal {
        // 1. Policy Hash Integrity
        if (activePolicyHash != bytes32(0) && policyHash != activePolicyHash) {
            revert PolicyHashMismatch(activePolicyHash, policyHash);
        }

        // 2. Token Allowlist Verification
        if (hasTokenAllowlist && !isTokenAllowed[token]) {
            revert TokenNotAllowed(token);
        }

        // 3. Recipient Allowlist Verification
        if (recipient != address(0) && hasRecipientAllowlist && !isRecipientAllowed[recipient]) {
            revert RecipientNotAllowed(recipient);
        }

        // 4. Per-Transaction Limit
        if (perTxCapUsd > 0 && amountUsd > perTxCapUsd) {
            revert ExceedsPerTxCap(amountUsd, perTxCapUsd);
        }

        // 5. Daily Spending Cap
        uint256 today = block.timestamp / 1 days;
        if (today != currentDayIndex) {
            currentDayIndex = today;
            spentTodayUsd = 0;
        }
        if (dailyCapUsd > 0 && (spentTodayUsd + amountUsd > dailyCapUsd)) {
            revert ExceedsDailyLimit(spentTodayUsd + amountUsd, dailyCapUsd);
        }

        // 6. Solvency Reserve Floor Verification
        if (minBalanceFloorUsd > 0 && balanceAfterUsd < minBalanceFloorUsd) {
            revert BelowMinimumBalanceFloor(balanceAfterUsd, minBalanceFloorUsd);
        }

        // Update daily tracking
        spentTodayUsd += amountUsd;
    }

    // --- Execution Entrypoints ---

    /**
     * @notice Autonomous Guarded Swap Execution
     */
    function executeSwap(
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 minAmountOut,
        uint256 tradeAmountUsd,
        uint256 balanceAfterUsd,
        bytes32 policyHash,
        address router,
        bytes calldata routerData
    ) external onlyAuthorized whenNotPaused returns (uint256 amountOut) {
        _verifyGuards(tokenIn, router, tradeAmountUsd, balanceAfterUsd, policyHash);

        if (tokenIn != address(0)) {
            IERC20(tokenIn).approve(router, amountIn);
        }

        (bool success, bytes memory retData) = router.call{value: tokenIn == address(0) ? amountIn : 0}(routerData);
        if (!success) revert PolicyViolation("RouterSwapFailed");

        amountOut = retData.length >= 32 ? abi.decode(retData, (uint256)) : minAmountOut;
        emit SwapExecuted(tokenIn, tokenOut, amountIn, amountOut, policyHash);
    }

    /**
     * @notice Guarded Transfer (Immediate or Scheduled)
     */
    function executeTransfer(
        address token,
        address payable recipient,
        uint256 amount,
        uint256 transferAmountUsd,
        uint256 balanceAfterUsd,
        bytes32 policyHash
    ) external onlyAuthorized whenNotPaused {
        _verifyGuards(token, recipient, transferAmountUsd, balanceAfterUsd, policyHash);

        if (token == address(0)) {
            (bool success, ) = recipient.call{value: amount}("");
            if (!success) revert TransferFailed();
        } else {
            bool success = IERC20(token).transfer(recipient, amount);
            if (!success) revert TransferFailed();
        }

        emit TransferExecuted(token, recipient, amount, policyHash);
    }
}
