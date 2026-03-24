import logging
import aiohttp
from fastmcp import FastMCP

from qotbot.utils.config import WEB_TIMEOUT

logger = logging.getLogger(__name__)

woolworths_tools = FastMCP("Woolworths NZ")


@woolworths_tools.tool
async def search_products(
    query: str,
    size: int = 48,
    in_stock_only: bool = False,
) -> str:
    """
    Search for products on Woolworths NZ.

    Args:
        query: Search term (e.g., "Bread", "Milk")
        size: Number of results to return (default 48)
        in_stock_only: If True, only return products in stock

    Returns:
        Formatted text string with product details
    """
    api_url = "https://www.woolworths.co.nz/api/v1/products"
    params = {
        "target": "search",
        "search": query,
        "inStockProductsOnly": str(in_stock_only),
        "size": str(size),
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-NZ,en;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Referer": "https://www.woolworths.co.nz/",
        "Content-Type": "application/json",
        "X-Requested-With": "OnlineShopping.WebApp",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Expires": "Sat, 01 Jan 2000 00:00:00 GMT",
        "x-ui-ver": "7.73.30",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    timeout = aiohttp.ClientTimeout(total=WEB_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url, params=params, headers=headers) as resp:
                resp.raise_for_status()
                logger.info(f"Woolworths API response status: {resp.status}")
                data = await resp.json()
                logger.debug(
                    f"Woolworths API response keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
                )

                products_data = data.get("products")
                if not products_data:
                    logger.warning(
                        f"No 'products' key in API response. Full response: {data}"
                    )
                    return "No products found"

                products = products_data.get("items", [])
                logger.info(f"Products count in response: {len(products)}")
                if not products:
                    logger.warning(f"Empty products list for query '{query}'")
                    return "No products found"

                output = []
                for product in products:
                    if product.get("type") != "Product":
                        continue
                    name = product.get("name", "Unknown")
                    price = product.get("price", {}).get("salePrice", "N/A")
                    availability = product.get("availabilityStatus", "Unknown")
                    slug = product.get("slug", "")
                    image_url = product.get("images", {}).get("small", "N/A")
                    product_url = (
                        f"https://www.woolworths.co.nz/shop/products/{slug}"
                        if slug
                        else "N/A"
                    )

                    output.append(
                        f"Name: {name}\n"
                        f"Price: ${price}\n"
                        f"Availability: {availability}\n"
                        f"URL: {product_url}\n"
                        f"Image: {image_url}\n"
                    )

                return f"Found {len(output)} products:\n\n" + "\n".join(output)
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP error from Woolworths API: {e}")
        return f"Error from Woolworths API: {str(e)}"
    except Exception as e:
        logger.error(f"Failed to search products: {e}")
        return f"Failed to search products: {str(e)}"


if __name__ == "__main__":
    woolworths_tools.run()
