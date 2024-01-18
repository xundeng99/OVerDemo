interface ISimpleAMM {
    function balanceETH() external view returns (uint256);

    function balanceUSDC() external view returns (uint256);

    function priceUSDCETH() external view returns (uint256);

    function priceETHUSDC() external view returns (uint256);

    function getEstimatedEthForUSDC(uint256 amountFrom)
        external
        view
        returns (uint256);

    function getEstimatedUSDCForEth(uint256 amountFrom)
        external
        view
        returns (uint256);

    function swap(address fromToken, uint256 amountFrom)
        external
        payable
        returns (uint256);
}
interface IERC20 {
    event Transfer(address indexed from, address indexed to, uint256 value);

    event Approval(
        address indexed owner,
        address indexed spender,
        uint256 value
    );

    function totalSupply() external view returns (uint256);

    function balanceOf(address account) external view returns (uint256);

    function transfer(address to, uint256 amount) external returns (bool);

    function allowance(address owner, address spender)
        external
        view
        returns (uint256);

    function approve(address spender, uint256 amount) external returns (bool);

    function transferFrom(
        address from,
        address to,
        uint256 amount
    ) external returns (bool);
}


contract SimpleLender {
    address public USDCAddress;
    address public ammAddress;
    uint16 public collateralizationRatio;
    mapping(address => uint256) public USDCdeposits;

    constructor(
        address usdc,
        address amm,
        uint16 collat
    )  public {
        USDCAddress = usdc;
        ammAddress = amm;
        collateralizationRatio = collat; // in basis points
    }

    function depositUSDC(uint256 amount) external {
        IERC20(USDCAddress).transferFrom(msg.sender, address(this), amount);
        USDCdeposits[msg.sender] += amount;
    }

    // OVer: oracle price function getPriceUSDCETH
    function getPriceUSDCETH() public view returns (uint256) {
        // (Vulnerable) External call to AMM used as price oracle
        return ISimpleAMM(ammAddress).priceUSDCETH();
    }

    // OVer: critical computation
    function maxBorrowAmount() public view returns (uint256) {
        // Does not take into consideration any exisitng borrows (collateral already used)
        uint256 depositedUSDC = USDCdeposits[msg.sender];
    
        uint256 equivalentEthValue = (depositedUSDC * getPriceUSDCETH() ) / 1e18;
        
        // Max borrow amount = (collateralizationRatio/10000) * eth value of deposited USDC

        return (equivalentEthValue * collateralizationRatio) / 10000;
    }

    // OVer: entry point of analysis and contains require statements
    function borrowETH(uint256 amount) external {
        // Does not take into consideration any exisitng borrows
        require(
            amount <= maxBorrowAmount(),
            "amount exceeds max borrow amount"
        );
        (bool success, ) = msg.sender.call{value: amount}(new bytes(0));
        require(success, "Failed to transfer ETH");
    }

    receive() external payable {}
}
