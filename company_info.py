"""Company descriptions for SEO stock pages."""
COMPANY_INFO = {
    "NVDA": ("NVIDIA Corporation", "semiconductor",
        "NVIDIA designs graphics processing units (GPUs) for gaming, AI, and data centers. "
        "The company's CUDA platform dominates AI training and inference, making it the world's "
        "most valuable semiconductor company. Key products include H100/B200 GPUs, Grace CPUs, "
        "and the CUDA software ecosystem. Major customers: Microsoft, Amazon, Google, Meta."),
    "AAPL": ("Apple Inc.", "technology",
        "Apple designs iPhones, Macs, iPads, wearables, and services (App Store, Apple Music, iCloud). "
        "The world's largest company by market cap. Expanding into AI with Apple Intelligence and Vision Pro spatial computing."),
    "MSFT": ("Microsoft Corporation", "technology",
        "Microsoft is the world's largest software company, known for Windows, Office 365, Azure cloud, "
        "and GitHub. Major AI investor through OpenAI partnership. Azure is the #2 cloud platform behind AWS."),
    "GOOG": ("Alphabet Inc. (Google)", "technology",
        "Alphabet owns Google Search, YouTube, Android, Google Cloud, and Waymo self-driving. "
        "Dominates digital advertising. Investing heavily in AI through Gemini models and DeepMind."),
    "AMZN": ("Amazon.com Inc.", "e-commerce",
        "Amazon dominates e-commerce and cloud computing through AWS. Also operates Prime Video, "
        "Whole Foods, and Alexa. AWS generates the majority of operating profit despite smaller revenue share."),
    "META": ("Meta Platforms Inc.", "technology",
        "Meta owns Facebook, Instagram, WhatsApp, and Threads. Pivoting to AI and metaverse. "
        "Open-source LLM leader through Llama models. Digital advertising powerhouse."),
    "TSLA": ("Tesla Inc.", "automotive",
        "Tesla is the world's leading electric vehicle manufacturer. Also produces energy storage systems "
        "and solar products. Expanding into AI robotics (Optimus) and full self-driving technology."),
    "AMD": ("Advanced Micro Devices", "semiconductor",
        "AMD designs CPUs (Ryzen, EPYC) and GPUs (Radeon, Instinct) competing with Intel and NVIDIA. "
        "Growing AI presence with MI300X accelerators. Second-largest x86 CPU maker."),
    "AVGO": ("Broadcom Inc.", "semiconductor",
        "Broadcom designs networking chips, storage adapters, and enterprise software. Major supplier "
        "for Apple, data centers, and AI infrastructure. Acquired VMware for $69B in 2023."),
    "TSM": ("Taiwan Semiconductor Manufacturing Co.", "semiconductor",
        "TSMC is the world's largest contract chip manufacturer, making chips for Apple, NVIDIA, AMD, "
        "and Qualcomm. Leading in advanced 3nm/2nm process nodes. Critical to global AI supply chain."),
    "QCOM": ("Qualcomm Inc.", "semiconductor",
        "Qualcomm designs mobile processors (Snapdragon) and 5G modems. Dominates smartphone chipsets "
        "and expanding into automotive and IoT. Key supplier for Samsung and Chinese OEMs."),
    "INTC": ("Intel Corporation", "semiconductor",
        "Intel designs and manufactures x86 CPUs for PCs and servers. Building foundry business to compete "
        "with TSMC. Struggling with market share losses to AMD but remains the largest chipmaker by revenue."),
    "ARM": ("ARM Holdings", "semiconductor",
        "ARM designs CPU architectures used in 99% of smartphones. Expanding into data center CPUs (AWS "
        "Graviton, NVIDIA Grace) and AI inference. Licensing model generates royalty revenue per chip."),
    "MU": ("Micron Technology", "semiconductor",
        "Micron manufactures DRAM and NAND memory chips critical for AI servers, PCs, and smartphones. "
        "HBM3E memory is key for NVIDIA's AI GPUs. Benefits from AI-driven memory demand surge."),
    "COIN": ("Coinbase Global", "crypto",
        "Coinbase is the largest US cryptocurrency exchange. Offers trading, custody, and staking services. "
        "Revenue tied to crypto trading volumes and Bitcoin/Ethereum prices. Expanding internationally."),
    "MSTR": ("Strategy (formerly MicroStrategy)", "crypto",
        "Strategy is the largest corporate Bitcoin holder with 500K+ BTC. Originally a business intelligence "
        "software company, now primarily a Bitcoin treasury play. Stock trades as a leveraged BTC proxy."),
    "PLTR": ("Palantir Technologies", "technology",
        "Palantir builds AI-powered data analytics platforms (Gotham, Foundry, AIP) for government "
        "and enterprise. Known for defense/intelligence contracts. Growing commercial AI business rapidly."),
    "SOFI": ("SoFi Technologies", "fintech",
        "SoFi offers digital banking, student/car loans, investing, and credit cards. One-stop fintech "
        "platform targeting millennials. Recently obtained bank charter for expanded services."),
    "RKLB": ("Rocket Lab USA", "aerospace",
        "Rocket Lab provides small satellite launch services via Electron rocket. Building larger Neutron "
        "rocket for constellation launches. Competitor to SpaceX in dedicated small-payload launches."),
    "GME": ("GameStop Corp.", "retail",
        "GameStop is a video game retailer famous for the 2021 meme stock short squeeze. "
        "Transitioning to e-commerce and digital collectibles. Ryan Cohen leads turnaround strategy."),
    "BABA": ("Alibaba Group", "e-commerce",
        "Alibaba is China's largest e-commerce and cloud computing company. Operates Taobao, Tmall, "
        "AliExpress, and Alibaba Cloud. AI push through Tongyi Qianwen models."),
    "JD": ("JD.com", "e-commerce",
        "JD.com is China's second-largest e-commerce platform, competing with Alibaba and PDD. "
        "Known for authentic products and self-operated logistics network. Expanding internationally."),
    "NIO": ("NIO Inc.", "automotive",
        "NIO designs premium electric vehicles in China. Known for battery-swapping technology "
        "and the ET5/ET7 sedans. Expanding to Europe. Competes with Tesla and BYD in China's EV market."),
    "SMCI": ("Super Micro Computer", "technology",
        "Super Micro builds high-performance servers for AI, cloud, and data centers. Key NVIDIA partner "
        "for GPU server systems. Revenue surging with AI infrastructure buildout."),
    "MARA": ("MARA Holdings", "crypto",
        "MARA is one of the largest publicly traded Bitcoin mining companies. Operates mining facilities "
        "across the US. Stock acts as a leveraged Bitcoin proxy with mining operational leverage."),
}

def get_company_info(symbol: str) -> tuple:
    """Returns (name, sector, description) or (symbol, 'other', generic_desc)."""
    if symbol in COMPANY_INFO:
        return COMPANY_INFO[symbol]
    return (f"{symbol} Inc.", "other",
        f"{symbol} is a publicly traded company. Live price data from Yahoo Finance. "
        f"Visit the {symbol} investor relations page for detailed financial information.")
