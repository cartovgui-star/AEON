"""
Additional Data API Routes
Social data, on-chain stats, fees, gas prices, DeFi TVL
"""

from fastapi import APIRouter

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/social/{symbol}")
async def api_social_data(symbol: str = "BTC"):
    """Get social stats from CryptoCompare"""
    from additional_data import additional_data
    return await additional_data.get_crypto_compare_social(symbol.upper())


@router.get("/btc/onchain")
async def api_btc_onchain():
    """Get BTC on-chain stats from Blockchain.com"""
    from additional_data import additional_data
    return await additional_data.get_blockchain_btc_stats()


@router.get("/btc/fees")
async def api_btc_fees():
    """Get BTC mempool fee estimates"""
    from additional_data import additional_data
    return await additional_data.get_mempool_fees()


@router.get("/eth/gas")
async def api_eth_gas():
    """Get ETH gas prices"""
    from additional_data import additional_data
    return await additional_data.get_eth_gas()


@router.get("/defi/tvl")
async def api_defi_tvl(protocol: str = None):
    """Get DeFi TVL from DefiLlama"""
    from additional_data import additional_data
    return await additional_data.get_defi_llama_tvl(protocol)


@router.get("/all/{symbol}")
async def api_all_additional_data(symbol: str = "BTC"):
    """Get all additional data sources combined"""
    from additional_data import additional_data
    return await additional_data.get_full_additional_data(symbol.upper())
