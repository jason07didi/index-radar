/* =========================================================
   INDEX RADAR
   Frontend Strategy Engine 4.0
   VALUATION FIRST

   核心原则：

   1. 估值决定：
      - 定投
      - 持有
      - 暂停新增
      - 再平衡

   2. 估值程度决定：
      - 定期不定额投入金额

   3. 价格位置 / 市场情绪 / 技术状态 / 20日情境：
      - 只用于解释当前市场环境
      - 不进入长期核心决策

   4. 持仓盈亏：
      - 不作为买卖依据

   ========================================================= */


/* =========================================================
   GLOBAL
   ========================================================= */

let marketData = null;

let currentIndex = "sse50";

let currentChartRange = 252;

let marketChart = null;

let activeHelpButton = null;


const DATA_URL =
    "data/market.json";


const REFRESH_INTERVAL =
    5 * 60 * 1000;


/* =========================================================
   BASIC UTILITIES
   ========================================================= */

function $(id) {

    return document.getElementById(id);

}


function clamp(
    value,
    min,
    max
) {

    return Math.max(
        min,
        Math.min(
            max,
            value
        )
    );

}


function safeNumber(
    value,
    fallback = null
) {

    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {

        return fallback;

    }


    const number =
        Number(value);


    return Number.isFinite(number)
        ? number
        : fallback;

}


function formatNumber(
    value,
    digits = 2
) {

    const number =
        safeNumber(
            value,
            null
        );


    if (number === null) {

        return "--";

    }


    return number.toLocaleString(

        "zh-CN",

        {
            minimumFractionDigits:
                digits,

            maximumFractionDigits:
                digits
        }

    );

}


function formatCompactNumber(
    value,
    maxDigits = 2
) {

    const number =
        safeNumber(
            value,
            null
        );


    if (number === null) {

        return "--";

    }


    return number.toLocaleString(

        "zh-CN",

        {
            maximumFractionDigits:
                maxDigits
        }

    );

}


function formatPercent(
    value,
    digits = 2,
    showPlus = true
) {

    const number =
        safeNumber(
            value,
            null
        );


    if (number === null) {

        return "--";

    }


    const prefix =
        (
            showPlus
            &&
            number > 0
        )
            ? "+"
            : "";


    return (

        prefix

        +

        number.toFixed(
            digits
        )

        +

        "%"

    );

}


function formatPlainPercent(
    value,
    digits = 2
) {

    const number =
        safeNumber(
            value,
            null
        );


    if (number === null) {

        return "--";

    }


    return (

        number.toFixed(
            digits
        )

        +

        "%"

    );

}


function formatCurrency(
    value
) {

    const number =
        safeNumber(
            value,
            null
        );


    if (number === null) {

        return "--";

    }


    return (

        "¥"

        +

        Math.round(
            number
        )
        .toLocaleString(
            "zh-CN"
        )

    );

}


function setText(
    id,
    value
) {

    const element =
        $(id);


    if (!element) {

        return;

    }


    element.textContent =
        (
            value === null
            ||
            value === undefined
            ||
            value === ""
        )
            ? "--"
            : String(value);

}


function setPercentBar(
    id,
    value
) {

    const element =
        $(id);


    if (!element) {

        return;

    }


    const number =
        clamp(
            safeNumber(
                value,
                0
            ),
            0,
            100
        );


    element.style.width =
        "0%";


    requestAnimationFrame(

        () => {

            element.style.width =
                `${number}%`;

        }

    );

}


/* =========================================================
   SOURCE QUALITY
   ========================================================= */

function humanSourceQuality(
    quality
) {

    switch (quality) {

        case "official":

            return "官方";


        case "secondary":

            return "二级可靠来源";


        case "proxy":

            return "ETF代理";


        case "accumulated":

            return "历史积累";


        default:

            return quality || "--";

    }

}


/* =========================================================
   VALUATION METHOD SHORT NAME
   ========================================================= */

function getMethodShortName(
    indexKey,
    valuation
) {

    if (
        indexKey === "sse50"
    ) {

        return "盈利收益率法";

    }


    if (
        indexKey === "sp500"
    ) {

        return "博格公式框架";

    }


    if (
        indexKey === "nasdaq100"
    ) {

        return "成长型博格框架";

    }


    return (
        valuation.method_name
        || "--"
    );

}


/* =========================================================
   VALUATION STATE
   ========================================================= */

function getValuationSignal(
    state
) {

    switch (state) {

        case "明显低估":

            return "deep-undervalued";


        case "低估":

            return "undervalued";


        case "合理":

            return "fair";


        case "偏高估":

            return "expensive";


        case "明显高估":

            return "overvalued";


        case "PE异常/需辅助估值":

            return "uncertain";


        default:

            return "unknown";

    }

}


/* =========================================================
   VALUATION DESCRIPTION
   ========================================================= */

function buildValuationDescription(
    data
) {

    const valuation =
        data.valuation
        || {};


    const state =
        valuation.state
        || "数据不足";


    const method =
        getMethodShortName(
            currentIndex,
            valuation
        );


    const confidence =
        valuation.confidence
        || "较低";


    if (
        state === "明显低估"
    ) {

        return (

            `按${method}判断，当前估值已进入历史较低区域。`

            +

            `在现有数据口径下，估值参考可信度为${confidence}。`

            +

            "长期策略以增强定投为主；短期继续下跌并不会自动推翻低估结论。"

        );

    }


    if (
        state === "低估"
    ) {

        return (

            `按${method}判断，当前估值处于相对低估区域。`

            +

            "符合继续定投的条件。"

            +

            "投入金额可以随估值进一步降低而增加，而不是等待技术指标确认。"

        );

    }


    if (
        state === "合理"
    ) {

        return (

            `按${method}判断，当前估值已经回到相对合理区域。`

            +

            "依据当前模型，已有持仓以继续持有为主，暂停估值驱动的新增资金。"

        );

    }


    if (
        state === "偏高估"
    ) {

        return (

            `按${method}判断，当前估值已高于较合理的历史区域。`

            +

            "现阶段不适合继续新增长期资金，但偏高估本身也不意味着短期一定下跌。"

        );

    }


    if (
        state === "明显高估"
    ) {

        return (

            `按${method}判断，当前估值处于自身历史较高区域。`

            +

            "暂停新增；如果实际配置比例已经明显高于长期目标，可考虑分批再平衡，"

            +

            "而不是依据单日走势一次性退出。"

        );

    }


    if (
        state === "PE异常/需辅助估值"
    ) {

        return (

            "当前PE可能受到盈利异常变化影响，单独使用PE容易形成误判。"

            +

            "系统因此主动降低PE的决策权，等待PB、正常化盈利等辅助估值数据。"

        );

    }


    return (

        "当前估值数据或历史样本不足，"

        +

        "系统不会为了给出结论而人为补齐缺失信息。"

    );

}


/* =========================================================
   CORE CONCLUSION
   ========================================================= */

function buildCoreConclusion(
    data
) {

    const valuation =
        data.valuation
        || {};


    const state =
        valuation.state
        || "数据不足";


    const pe =
        safeNumber(
            valuation.pe,
            null
        );


    const percentile =
        safeNumber(
            valuation.pe_percentile_10y,
            null
        );


    let metrics = "";


    if (
        pe !== null
        &&
        percentile !== null
    ) {

        metrics =

            ` 当前可比口径PE约为 ${pe.toFixed(2)}，`

            +

            `位于可用历史约 ${percentile.toFixed(1)}% 分位。`;

    }


    return (

        buildValuationDescription(
            data
        )

        +

        metrics

        +

        " 价格位置、风险情绪、技术状态和短期20日情境均只作为辅助观察。"

    );

}


/* =========================================================
   RISK / CAPITAL INTENSITY
   ========================================================= */

function getInvestmentN(
    risk
) {

    switch (risk) {

        case "conservative":

            return 0.5;


        case "aggressive":

            return 1.5;


        case "balanced":
        default:

            return 1.0;

    }

}


function getRiskLabel(
    risk
) {

    switch (risk) {

        case "conservative":

            return "保守";


        case "aggressive":

            return "积极";


        default:

            return "均衡";

    }

}


/* =========================================================
   USER SETTINGS
   ========================================================= */

function storageKey(
    field
) {

    return (

        "indexRadar4_"

        +

        currentIndex

        +

        "_"

        +

        field

    );

}


function loadUserSettings() {

    const base =
        localStorage.getItem(

            storageKey(
                "baseInvestment"
            )

        );


    const max =
        localStorage.getItem(

            storageKey(
                "maxInvestment"
            )

        );


    const risk =
        localStorage.getItem(

            storageKey(
                "risk"
            )

        );


    if (
        $("baseInvestmentInput")
    ) {

        $("baseInvestmentInput").value =

            base !== null

                ? base

                : 3000;

    }


    if (
        $("maxInvestmentInput")
    ) {

        $("maxInvestmentInput").value =

            max !== null

                ? max

                : 6000;

    }


    if (
        $("riskSelect")
    ) {

        $("riskSelect").value =

            risk

            || "balanced";

    }


    updateRiskDescription();

}


function saveUserSettings() {

    if (
        $("baseInvestmentInput")
    ) {

        localStorage.setItem(

            storageKey(
                "baseInvestment"
            ),

            $("baseInvestmentInput").value

        );

    }


    if (
        $("maxInvestmentInput")
    ) {

        localStorage.setItem(

            storageKey(
                "maxInvestment"
            ),

            $("maxInvestmentInput").value

        );

    }


    if (
        $("riskSelect")
    ) {

        localStorage.setItem(

            storageKey(
                "risk"
            ),

            $("riskSelect").value

        );

    }

}


function updateRiskDescription() {

    if (
        !$("riskSelect")
        ||
        !$("riskNDescription")
    ) {

        return;

    }


    const risk =
        $("riskSelect").value;


    const n =
        getInvestmentN(
            risk
        );


    setText(

        "riskNDescription",

        `${getRiskLabel(risk)}模式：n = ${n.toFixed(1)}；只改变低估时资金放大程度，不改变估值结论。`

    );

}


/* =========================================================
   PERIODIC VARIABLE INVESTMENT
   ========================================================= */

function calculateInvestmentPlan(
    data
) {

    const valuation =
        data.valuation
        || {};


    const state =
        valuation.state
        || "数据不足";


    const formula =
        valuation.investment_formula
        || {};


    const baseInvestment =
        Math.max(

            0,

            safeNumber(
                $("baseInvestmentInput")
                    ? $("baseInvestmentInput").value
                    : 3000,

                3000
            )

        );


    let maxInvestment =
        Math.max(

            0,

            safeNumber(
                $("maxInvestmentInput")
                    ? $("maxInvestmentInput").value
                    : 6000,

                6000
            )

        );


    if (
        maxInvestment === 0
    ) {

        maxInvestment =
            Number.POSITIVE_INFINITY;

    }


    const risk =
        $("riskSelect")
            ? $("riskSelect").value
            : "balanced";


    const n =
        getInvestmentN(
            risk
        );


    let multiplier = null;

    let recommendedInvestment = null;

    let formulaText = "";

    let action =
        valuation.action
        || "估值数据不足，暂不判断";


    let explanation = "";


    /* =====================================================
       DATA INVALID / PE ABNORMAL
       ===================================================== */

    if (
        state === "数据不足"
        ||
        state === "PE异常/需辅助估值"
        ||
        valuation.core_decision_enabled === false
    ) {

        multiplier =
            null;


        recommendedInvestment =
            null;


        formulaText =
            "当前估值数据不足或PE可靠性不足，定期不定额公式暂不启用。";


        explanation =
            (
                state === "PE异常/需辅助估值"
            )

                ? (
                    "当前PE可能受到盈利异常波动影响，"
                    +
                    "因此不使用一个可能失真的PE去计算定投金额。"
                )

                : (
                    "当前历史估值样本不足，"
                    +
                    "系统暂不计算投资金额，避免制造虚假精度。"
                );


        return {

            state,

            action,

            baseInvestment,

            maxInvestment,

            risk,

            n,

            multiplier,

            recommendedInvestment,

            formulaText,

            explanation

        };

    }


    /* =====================================================
       FAIR / EXPENSIVE

       PDF理论：
       合理估值 -> 持有，停止新增
       高估 -> 停止新增 / 分批再平衡
       ===================================================== */

    if (
        state === "合理"
        ||
        state === "偏高估"
        ||
        state === "明显高估"
    ) {

        multiplier =
            0;


        recommendedInvestment =
            0;


        formulaText =
            "当前不处于低估定投区，估值调整公式暂不启用。";


        if (
            state === "合理"
        ) {

            explanation =
                (
                    "当前估值位于相对合理区域。"
                    +
                    "依据估值定投框架，本期估值驱动新增金额为0，"
                    +
                    "已有份额继续持有。"
                );


        } else if (
            state === "偏高估"
        ) {

            explanation =
                (
                    "当前估值已经偏高。"
                    +
                    "本期暂停新增长期资金，继续观察基本面和估值变化。"
                );


        } else {

            explanation =
                (
                    "当前估值处于明显高估区域。"
                    +
                    "停止新增；若实际配置比例明显高于长期目标，"
                    +
                    "可考虑分批再平衡。"
                );

        }


        return {

            state,

            action,

            baseInvestment,

            maxInvestment,

            risk,

            n,

            multiplier,

            recommendedInvestment,

            formulaText,

            explanation

        };

    }


    /* =====================================================
       UNDERVALUED
       ===================================================== */

    const formulaType =
        formula.type
        || valuation.primary_method;


    const currentPE =
        safeNumber(
            valuation.pe,
            null
        );


    const currentEY =
        safeNumber(
            valuation.earnings_yield_pct,
            null
        );


    const entryPE =
        safeNumber(
            formula.entry_pe,
            null
        );


    const entryEY =
        safeNumber(
            formula.entry_earnings_yield_pct,
            null
        );


    /* =====================================================
       EARNINGS YIELD METHOD

       A_t = A_0 × (EY_t / EY_0)^n
       ===================================================== */

    if (
        formulaType === "earnings_yield"
        &&
        currentEY !== null
        &&
        entryEY !== null
        &&
        currentEY > 0
        &&
        entryEY > 0
    ) {

        const rawRatio =
            currentEY
            /
            entryEY;


        multiplier =
            Math.pow(
                rawRatio,
                n
            );


        multiplier =
            Math.max(
                1,
                multiplier
            );


        formulaText =

            `Aₜ = A₀ × (EYₜ / EY₀)^n = `

            +

            `${formatCurrency(baseInvestment)} × `

            +

            `(${currentEY.toFixed(2)}% / ${entryEY.toFixed(2)}%)^${n.toFixed(1)}`;


    /* =====================================================
       BOGLE PE METHOD

       A_t = A_0 × (PE_0 / PE_t)^n
       ===================================================== */

    } else if (
        (
            formulaType === "pe"
            ||
            formulaType === "bogle_pe"
        )
        &&
        currentPE !== null
        &&
        entryPE !== null
        &&
        currentPE > 0
        &&
        entryPE > 0
    ) {

        const rawRatio =
            entryPE
            /
            currentPE;


        multiplier =
            Math.pow(
                rawRatio,
                n
            );


        multiplier =
            Math.max(
                1,
                multiplier
            );


        formulaText =

            `Aₜ = A₀ × (PE₀ / PEₜ)^n = `

            +

            `${formatCurrency(baseInvestment)} × `

            +

            `(${entryPE.toFixed(2)} / ${currentPE.toFixed(2)})^${n.toFixed(1)}`;


    /* =====================================================
       FORMULA MISSING
       ===================================================== */

    } else {

        multiplier =
            1;


        formulaText =
            (
                "当前估值已处于低估区，但估值锚点暂不完整；"
                +
                "本期仅按基础定投金额执行，不额外放大。"
            );

    }


    recommendedInvestment =
        baseInvestment
        *
        multiplier;


    if (
        Number.isFinite(
            maxInvestment
        )
    ) {

        recommendedInvestment =
            Math.min(

                recommendedInvestment,

                maxInvestment

            );

    }


    recommendedInvestment =
        Math.round(

            recommendedInvestment
            /
            10

        ) * 10;


    const actualMultiplier =
        (
            baseInvestment > 0
        )

            ? (
                recommendedInvestment
                /
                baseInvestment
            )

            : multiplier;


    multiplier =
        actualMultiplier;


    if (
        state === "明显低估"
    ) {

        explanation =

            `当前处于明显低估区域，符合增强定投条件。`

            +

            `按照${getRiskLabel(risk)}资金强度（n=${n.toFixed(1)}）计算，`

            +

            `本期估值调整后约为基础金额的 ${multiplier.toFixed(2)} 倍。`

            +

            "短期走势继续下跌不会自动停止这一定投逻辑。";


    } else {

        explanation =

            `当前处于低估区域，符合继续定投条件。`

            +

            `按照${getRiskLabel(risk)}资金强度（n=${n.toFixed(1)}）执行定期不定额，`

            +

            `本期约为基础金额的 ${multiplier.toFixed(2)} 倍。`;

    }


    return {

        state,

        action,

        baseInvestment,

        maxInvestment,

        risk,

        n,

        multiplier,

        recommendedInvestment,

        formulaText,

        explanation

    };

}


/* =========================================================
   FETCH MARKET DATA
   ========================================================= */

async function loadMarketData() {

    try {

        const response =
            await fetch(

                `${DATA_URL}?t=${Date.now()}`,

                {
                    cache:
                        "no-store"
                }

            );


        if (!response.ok) {

            throw new Error(
                `HTTP ${response.status}`
            );

        }


        marketData =
            await response.json();


        setText(

            "updatedAt",

            marketData.updated_at
            || "--"

        );


        renderGuideDynamicText();

        renderCurrentIndex();


    } catch (error) {

        console.error(
            "Index Radar 数据加载失败：",
            error
        );


        setText(

            "coreConclusion",

            "市场与估值数据加载失败，请稍后刷新页面。"

        );

    }

}


/* =========================================================
   CURRENT DATA
   ========================================================= */

function getCurrentData() {

    if (
        !marketData
        ||
        !marketData.indices
    ) {

        return null;

    }


    return (
        marketData.indices[
            currentIndex
        ]
        || null
    );

}


/* =========================================================
   VALUATION HERO
   ========================================================= */

function renderValuationHero(
    data
) {

    const valuation =
        data.valuation
        || {};


    const state =
        valuation.state
        || "数据不足";


    const signal =
        getValuationSignal(
            state
        );


    setText(
        "valuationState",
        state
    );


    setText(
        "valuationStateBadge",
        state
    );


    setText(
        "valuationAction",
        valuation.action
        || "--"
    );


    setText(
        "valuationDecisionDescription",
        buildValuationDescription(
            data
        )
    );


    setText(
        "valuationMethod",
        valuation.method_name
        || "--"
    );


    setText(
        "valuationMethodShort",
        getMethodShortName(
            currentIndex,
            valuation
        )
    );


    setText(
        "valuationConfidence",
        valuation.confidence
        || "--"
    );


    setText(
        "peReliability",
        valuation.pe_reliability
        || "--"
    );


    /* =====================================================
       BADGE
       ===================================================== */

    const badge =
        $("valuationStateBadge");


    if (badge) {

        badge.className =
            "valuation-state-badge";


        badge.classList.add(
            `valuation-${signal}`
        );

    }


    /* =====================================================
       SIGNAL
       ===================================================== */

    const signalElement =
        $("valuationSignal");


    if (signalElement) {

        signalElement.className =
            "valuation-signal";


        signalElement.classList.add(
            `valuation-signal-${signal}`
        );

    }


    /* =====================================================
       CORE VALUES
       ===================================================== */

    setText(
        "valuationPE",
        formatNumber(
            valuation.pe,
            2
        )
    );


    setText(
        "earningsYield",
        formatPlainPercent(
            valuation.earnings_yield_pct,
            2
        )
    );


    setText(
        "pePercentile",

        valuation.pe_percentile_10y !== null
        &&
        valuation.pe_percentile_10y !== undefined

            ? (
                `${Number(
                    valuation.pe_percentile_10y
                ).toFixed(1)}%`
            )

            : "--"

    );


    setText(
        "dividendYield",
        formatPlainPercent(
            valuation.dividend_yield_pct,
            2
        )
    );


    if (
        currentIndex === "sse50"
    ) {

        setText(
            "valuationPEHint",
            "上交所官方月报口径，非严格PE-TTM"
        );


        setText(
            "dividendYieldHint",
            "当前可靠自动化数据暂缺"
        );


    } else {

        setText(
            "valuationPEHint",
            "指数历史口径；ETF PE仅作交叉校验"
        );


        setText(
            "dividendYieldHint",
            "ETF代理股息率"
        );

    }


    setText(
        "coreConclusion",
        buildCoreConclusion(
            data
        )
    );

}


/* =========================================================
   VALUATION RANGE
   ========================================================= */

function renderValuationRange(
    data
) {

    const valuation =
        data.valuation
        || {};


    setText(
        "valuationRangeState",
        valuation.state
        || "--"
    );


    setText(
        "valuationRangePE",
        formatNumber(
            valuation.pe,
            2
        )
    );


    const percentile =
        safeNumber(
            valuation.pe_percentile_10y,
            null
        );


    const marker =
        $("valuationScaleMarker");


    if (marker) {

        if (
            percentile === null
        ) {

            marker.style.display =
                "none";


        } else {

            marker.style.display =
                "";


            marker.style.left =
                `${clamp(
                    percentile,
                    0,
                    100
                )}%`;

        }

    }


    const band =
        valuation.pe_band
        || {};


    setText(
        "peBand20",
        `P20 ${formatNumber(
            band.p20,
            2
        )}`
    );


    setText(
        "peBand40",
        `P40 ${formatNumber(
            band.p40,
            2
        )}`
    );


    setText(
        "peBand60",
        `P60 ${formatNumber(
            band.p60,
            2
        )}`
    );


    setText(
        "peBand80",
        `P80 ${formatNumber(
            band.p80,
            2
        )}`
    );


    setText(
        "valuationHistoryCount",
        valuation.history_count
        ?? "--"
    );


    setText(
        "valuationHistoryWindow",
        valuation.history_window
        || "--"
    );

}


/* =========================================================
   RELATIVE VALUE
   ========================================================= */

function renderRelativeValue(
    data
) {

    const valuation =
        data.valuation
        || {};


    const ey =
        safeNumber(
            valuation.earnings_yield_pct,
            null
        );


    const bond =
        safeNumber(
            valuation.risk_free_yield_pct,
            null
        );


    const ratio =
        safeNumber(
            valuation.earnings_yield_to_bond,
            null
        );


    const spread =
        safeNumber(
            valuation.earnings_yield_minus_bond_pct,
            null
        );


    setText(
        "relativeEarningsYield",
        formatPlainPercent(
            ey,
            2
        )
    );


    if (
        currentIndex === "sse50"
    ) {

        setText(
            "riskFreeLabel",
            "中国10年国债"
        );


    } else {

        setText(
            "riskFreeLabel",
            "美国10年国债"
        );

    }


    setText(
        "riskFreeYield",
        formatPlainPercent(
            bond,
            3
        )
    );


    setText(

        "earningsYieldBondRatio",

        ratio !== null
            ? `${ratio.toFixed(2)}×`
            : "--"

    );


    setText(

        "earningsYieldBondSpread",

        spread !== null

            ? `${spread >= 0 ? "+" : ""}${spread.toFixed(2)} 个百分点`

            : "--"

    );


    if (
        ey === null
        ||
        bond === null
    ) {

        setText(

            "relativeValueDescription",

            "当前缺少完整的盈利收益率或国债收益率数据，因此不对股票与无风险资产的相对收益补偿作判断。"

        );


        return;

    }


    setText(

        "relativeValueDescription",

        (
            `当前指数盈利收益率约 ${ey.toFixed(2)}%，`

            +

            `10年期国债收益率约 ${bond.toFixed(2)}%，`

            +

            `两者相差 ${spread >= 0 ? "+" : ""}${spread.toFixed(2)} 个百分点。`

            +

            "该比较用于理解股票相对无风险资产的收益补偿，不单独决定买卖。"
        )

    );

}


/* =========================================================
   STRATEGY
   ========================================================= */

function renderInvestmentPlan(
    data
) {

    const plan =
        calculateInvestmentPlan(
            data
        );


    setText(
        "strategyAction",
        plan.action
    );


    setText(

        "recommendedInvestment",

        plan.recommendedInvestment === null

            ? "--"

            : formatCurrency(
                plan.recommendedInvestment
            )

    );


    setText(

        "investmentMultiplier",

        plan.multiplier === null

            ? "--"

            : `${plan.multiplier.toFixed(2)}×`

    );


    setText(
        "investmentN",
        plan.n.toFixed(1)
    );


    setText(
        "strategyText",
        plan.explanation
    );


    setText(
        "investmentFormulaText",
        plan.formulaText
    );


    /* =====================================================
       TAGS
       ===================================================== */

    const valuation =
        data.valuation
        || {};


    const tags = [

        `估值 ${valuation.state || "--"}`,

        `方法 ${getMethodShortName(
            currentIndex,
            valuation
        )}`,

        `可信度 ${valuation.confidence || "--"}`,

        `${getRiskLabel(plan.risk)} n=${plan.n.toFixed(1)}`

    ];


    const container =
        $("strategyTags");


    if (container) {

        container.innerHTML =
            "";


        tags.forEach(

            text => {

                const span =
                    document.createElement(
                        "span"
                    );


                span.className =
                    "strategy-tag";


                span.textContent =
                    text;


                container.appendChild(
                    span
                );

            }

        );

    }

}


/* =========================================================
   REASON LIST
   ========================================================= */

function renderTextList(
    id,
    items
) {

    const container =
        $(id);


    if (!container) {

        return;

    }


    container.innerHTML =
        "";


    const list =
        Array.isArray(
            items
        )
            ? items
            : [];


    if (
        list.length === 0
    ) {

        const row =
            document.createElement(
                "div"
            );


        row.className =
            "reason-row";


        row.textContent =
            "当前暂无可展示信息。";


        container.appendChild(
            row
        );


        return;

    }


    list.forEach(

        item => {

            const row =
                document.createElement(
                    "div"
                );


            row.className =
                "reason-row";


            const marker =
                document.createElement(
                    "span"
                );


            marker.className =
                "reason-marker";


            const text =
                document.createElement(
                    "span"
                );


            text.textContent =
                item;


            row.appendChild(
                marker
            );


            row.appendChild(
                text
            );


            container.appendChild(
                row
            );

        }

    );

}


/* =========================================================
   VALUATION REASONS
   ========================================================= */

function renderValuationReasons(
    data
) {

    const valuation =
        data.valuation
        || {};


    renderTextList(

        "valuationReasons",

        valuation.reasons
        || []

    );


    renderTextList(

        "valuationNotes",

        valuation.notes
        || []

    );

}


/* =========================================================
   PRICE POSITION
   ========================================================= */

function renderPricePosition(
    data
) {

    const position =
        data.price_position
        || {};


    setText(
        "pricePositionState",
        position.state
        || "--"
    );


    setText(

        "pricePositionScore",

        position.score !== null
        &&
        position.score !== undefined

            ? `${position.score}/100`

            : "--"

    );


    setText(
        "drawdown52w",
        formatPercent(
            data.drawdown_52w_pct,
            2
        )
    );


    setText(
        "devMa200",
        formatPercent(
            data.dev_ma200_pct,
            2
        )
    );

}


/* =========================================================
   SENTIMENT
   ========================================================= */

function renderSentiment(
    data
) {

    const sentiment =
        data.sentiment
        || {};


    setText(
        "sentimentLabel",
        sentiment.label
        || "市场风险情绪"
    );


    setText(
        "sentimentMainState",
        sentiment.state
        || "--"
    );


    setText(

        "sentimentMainScore",

        sentiment.score !== null
        &&
        sentiment.score !== undefined

            ? `${sentiment.score}/100`

            : "--"

    );


    setText(
        "sentimentSummary",
        sentiment.summary
        || "--"
    );


    const primary =
        sentiment.primary_indicator
        || {};


    setText(
        "sentimentPrimaryName",
        primary.name
        || "--"
    );


    setText(
        "sentimentPrimaryValue",
        formatCompactNumber(
            primary.value,
            2
        )
    );


    if (
        primary.percentile_5y !== null
        &&
        primary.percentile_5y !== undefined
    ) {

        setText(

            "sentimentPrimaryPercentile",

            `5年分位 ${Number(
                primary.percentile_5y
            ).toFixed(1)}%`

        );


    } else {

        setText(
            "sentimentPrimaryPercentile",
            ""
        );

    }

}


/* =========================================================
   TECHNICAL
   ========================================================= */

function renderTechnical(
    data
) {

    setText(
        "technicalState",
        data.technical_state
        || "--"
    );


    setText(

        "technicalScore",

        data.technical_score !== null
        &&
        data.technical_score !== undefined

            ? `${data.technical_score}/100`

            : "--"

    );


    setText(
        "rsi14",
        formatNumber(
            data.rsi14,
            1
        )
    );


    setText(
        "macdHist",
        formatNumber(
            data.macd_hist,
            2
        )
    );


    setText(
        "ma20",
        formatNumber(
            data.ma20,
            2
        )
    );


    setText(
        "ma60",
        formatNumber(
            data.ma60,
            2
        )
    );


    setText(
        "ma200",
        formatNumber(
            data.ma200,
            2
        )
    );


    setText(
        "technicalRsi14",
        formatNumber(
            data.rsi14,
            1
        )
    );


    setText(
        "technicalMacdHist",
        formatNumber(
            data.macd_hist,
            2
        )
    );


    setText(
        "volatility20",
        formatPlainPercent(
            data.volatility20,
            2
        )
    );

}


/* =========================================================
   HISTORICAL SCENARIO
   ========================================================= */

function buildScenarioDescription(
    probability
) {

    if (!probability) {

        return (
            "当前历史相似样本不足，暂时不展示20日情境统计。"
        );

    }


    const threshold =
        safeNumber(
            probability.direction_threshold_pct,
            3
        );


    return (

        `历史相似状态中，`

        +

        `未来20日上涨超过 ${threshold}% 的样本约占 ${probability.up_pct}%，`

        +

        `震荡约占 ${probability.sideways_pct}%，`

        +

        `下跌超过 ${threshold}% 的样本约占 ${probability.down_pct}%。`

        +

        "这只是历史条件频率，不参与长期估值决策。"

    );

}


function renderScenario(
    data
) {

    const probability =
        data.scenario_probability;


    if (!probability) {

        setText(
            "pathLabel",
            "样本不足"
        );


        setText(
            "pathDescription",
            buildScenarioDescription(
                null
            )
        );


        setText(
            "scenarioConfidence",
            "较低"
        );


        [
            "upProbability",
            "sidewaysProbability",
            "downProbability",
            "scenarioSampleSize",
            "effectiveSampleSize",
            "averageFutureReturn",
            "medianFutureReturn",
            "aboveMa20Probability",
            "aboveMa60Probability",
            "breakHighProbability",
            "breakLowProbability"
        ]
        .forEach(

            id => {

                setText(
                    id,
                    "--"
                );

            }

        );


        return;

    }


    setText(
        "pathLabel",
        probability.path_label
        || "--"
    );


    setText(
        "pathDescription",
        buildScenarioDescription(
            probability
        )
    );


    setText(
        "scenarioConfidence",
        probability.confidence
        || "--"
    );


    setText(
        "upProbability",
        `${probability.up_pct}%`
    );


    setText(
        "sidewaysProbability",
        `${probability.sideways_pct}%`
    );


    setText(
        "downProbability",
        `${probability.down_pct}%`
    );


    setPercentBar(
        "upProbabilityBar",
        probability.up_pct
    );


    setPercentBar(
        "sidewaysProbabilityBar",
        probability.sideways_pct
    );


    setPercentBar(
        "downProbabilityBar",
        probability.down_pct
    );


    setText(
        "scenarioSampleSize",
        probability.sample_size
        ?? "--"
    );


    setText(
        "effectiveSampleSize",
        probability.effective_sample_size
        ?? "--"
    );


    setText(
        "averageFutureReturn",
        formatPercent(
            probability.average_return_pct,
            2
        )
    );


    setText(
        "medianFutureReturn",
        formatPercent(
            probability.median_return_pct,
            2
        )
    );


    const events =
        probability.events
        || {};


    setText(

        "aboveMa20Probability",

        events.above_ma20_pct !== undefined

            ? `${events.above_ma20_pct}%`

            : "--"

    );


    setText(

        "aboveMa60Probability",

        events.above_ma60_pct !== undefined

            ? `${events.above_ma60_pct}%`

            : "--"

    );


    setText(

        "breakHighProbability",

        events.break_high20_pct !== undefined

            ? `${events.break_high20_pct}%`

            : "--"

    );


    setText(

        "breakLowProbability",

        events.break_low20_pct !== undefined

            ? `${events.break_low20_pct}%`

            : "--"

    );


    setText(
        "ma20Value",
        `MA20 ${formatNumber(
            data.ma20,
            2
        )}`
    );


    setText(
        "ma60Value",
        `MA60 ${formatNumber(
            data.ma60,
            2
        )}`
    );


    setText(
        "high20Value",
        `近20日高点 ${formatNumber(
            data.high20,
            2
        )}`
    );


    setText(
        "low20Value",
        `近20日低点 ${formatNumber(
            data.low20,
            2
        )}`
    );

}


/* =========================================================
   METHODOLOGY
   ========================================================= */

function renderMethodology(
    data
) {

    const valuation =
        data.valuation
        || {};


    setText(
        "methodologyName",
        valuation.method_name
        || "--"
    );


    if (
        currentIndex === "sse50"
    ) {

        setText(

            "methodologyDescription",

            "上证50采用盈利收益率法为主。盈利收益率越高，意味着单位企业盈利对应的价格越低；同时结合自身PE历史位置和中国10年期国债收益率理解当前估值环境。"

        );


    } else if (
        currentIndex === "sp500"
    ) {

        setText(

            "methodologyDescription",

            "标普500采用博格公式框架。当前版本以PE自身历史位置、盈利收益率与股息率为主要可自动化变量；盈利增长将作为后续重要基本面数据接入。"

        );


    } else {

        setText(

            "methodologyDescription",

            "纳斯达克100采用成长型博格框架。核心比较指数自身历史PE，而不是与上证50等盈利结构不同的指数机械比较绝对PE；盈利增长是后续需要继续完善的重要变量。"

        );

    }


    setText(
        "valuationSource",
        valuation.source
        || "--"
    );


    setText(
        "valuationSourceQuality",
        humanSourceQuality(
            valuation.source_quality
        )
    );


    const formula =
        valuation.investment_formula
        || {};


    if (
        formula.type === "earnings_yield"
    ) {

        setText(
            "methodologyFormula",
            "Aₜ = A₀ × (EYₜ / EY₀)ⁿ"
        );


    } else {

        setText(
            "methodologyFormula",
            "Aₜ = A₀ × (PE₀ / PEₜ)ⁿ"
        );

    }


    setText(
        "methodologyFormulaDescription",
        formula.description
        || "--"
    );

}


/* =========================================================
   CHART
   ========================================================= */

const CHART_COLORS = {

    price:
        "#183A56",

    ma20:
        "#BAC7D1",

    ma60:
        "#527B86",

    ma200:
        "#B08A54"

};


function renderChart(
    data
) {

    if (
        typeof Chart === "undefined"
    ) {

        console.warn(
            "Chart.js 尚未加载"
        );

        return;

    }


    const allHistory =
        Array.isArray(
            data.history
        )
            ? data.history
            : [];


    const history =
        allHistory.slice(
            -currentChartRange
        );


    if (
        history.length === 0
    ) {

        return;

    }


    const canvas =
        $("marketChart");


    if (!canvas) {

        return;

    }


    const ctx =
        canvas.getContext(
            "2d"
        );


    const gradient =
        ctx.createLinearGradient(
            0,
            0,
            0,
            560
        );


    gradient.addColorStop(
        0,
        "rgba(24,58,86,0.16)"
    );


    gradient.addColorStop(
        0.55,
        "rgba(24,58,86,0.045)"
    );


    gradient.addColorStop(
        1,
        "rgba(24,58,86,0)"
    );


    const labels =
        history.map(
            row =>
                row.date
        );


    const datasets = [

        {
            label:
                "收盘",

            data:
                history.map(
                    row =>
                        row.close
                ),

            borderColor:
                CHART_COLORS.price,

            backgroundColor:
                gradient,

            borderWidth:
                3.2,

            pointRadius:
                0,

            pointHoverRadius:
                4,

            pointHoverBackgroundColor:
                CHART_COLORS.price,

            pointHoverBorderColor:
                "#FFFFFF",

            pointHoverBorderWidth:
                2,

            borderCapStyle:
                "round",

            borderJoinStyle:
                "round",

            tension:
                0.20,

            fill:
                true,

            order:
                1
        },


        {
            label:
                "MA20",

            data:
                history.map(
                    row =>
                        row.ma20
                ),

            borderColor:
                CHART_COLORS.ma20,

            backgroundColor:
                CHART_COLORS.ma20,

            borderWidth:
                1.3,

            pointRadius:
                0,

            tension:
                0.22,

            spanGaps:
                true,

            fill:
                false,

            order:
                4
        },


        {
            label:
                "MA60",

            data:
                history.map(
                    row =>
                        row.ma60
                ),

            borderColor:
                CHART_COLORS.ma60,

            backgroundColor:
                CHART_COLORS.ma60,

            borderWidth:
                1.9,

            pointRadius:
                0,

            tension:
                0.22,

            spanGaps:
                true,

            fill:
                false,

            order:
                3
        },


        {
            label:
                "MA200 年线",

            data:
                history.map(
                    row =>
                        row.ma200
                ),

            borderColor:
                CHART_COLORS.ma200,

            backgroundColor:
                CHART_COLORS.ma200,

            borderWidth:
                2.6,

            pointRadius:
                0,

            tension:
                0.20,

            spanGaps:
                true,

            fill:
                false,

            order:
                2
        }

    ];


    if (
        marketChart
    ) {

        marketChart.destroy();

    }


    marketChart =
        new Chart(

            ctx,

            {

                type:
                    "line",


                data: {

                    labels,

                    datasets

                },


                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,


                    animation: {

                        duration:
                            500,

                        easing:
                            "easeOutQuart"

                    },


                    interaction: {

                        mode:
                            "index",

                        intersect:
                            false

                    },


                    plugins: {

                        legend: {

                            position:
                                "top",

                            align:
                                "start",

                            labels: {

                                usePointStyle:
                                    true,

                                pointStyle:
                                    "line",

                                boxWidth:
                                    28,

                                padding:
                                    20,

                                color:
                                    "#667782",

                                font: {

                                    size:
                                        11

                                }

                            }

                        },


                        tooltip: {

                            backgroundColor:
                                "rgba(17,43,62,0.96)",

                            titleColor:
                                "#FFFFFF",

                            bodyColor:
                                "rgba(255,255,255,0.82)",

                            cornerRadius:
                                13,

                            padding:
                                12,

                            usePointStyle:
                                true,


                            callbacks: {

                                label:
                                    function(
                                        context
                                    ) {

                                        const value =
                                            context.parsed.y;


                                        if (
                                            value === null
                                            ||
                                            value === undefined
                                        ) {

                                            return "";

                                        }


                                        return (

                                            `${context.dataset.label}  `

                                            +

                                            Number(
                                                value
                                            )
                                            .toLocaleString(

                                                "zh-CN",

                                                {
                                                    minimumFractionDigits:
                                                        2,

                                                    maximumFractionDigits:
                                                        2
                                                }

                                            )

                                        );

                                    }

                            }

                        }

                    },


                    scales: {

                        x: {

                            border: {

                                display:
                                    false

                            },


                            grid: {

                                display:
                                    false

                            },


                            ticks: {

                                color:
                                    "#89959D",

                                maxTicksLimit:
                                    currentChartRange >= 252
                                        ? 9
                                        : 7,

                                maxRotation:
                                    0,

                                autoSkip:
                                    true,

                                font: {

                                    size:
                                        10

                                },


                                callback:
                                    function(
                                        value
                                    ) {

                                        const label =
                                            this.getLabelForValue(
                                                value
                                            );


                                        if (
                                            currentChartRange >= 252
                                        ) {

                                            return (

                                                label.slice(
                                                    5,
                                                    7
                                                )

                                                +

                                                "月"

                                            );

                                        }


                                        return (
                                            label.slice(
                                                5
                                            )
                                        );

                                    }

                            }

                        },


                        y: {

                            grace:
                                "7%",


                            border: {

                                display:
                                    false

                            },


                            grid: {

                                color:
                                    "rgba(40,66,83,0.065)"

                            },


                            ticks: {

                                color:
                                    "#89959D",

                                padding:
                                    10,

                                font: {

                                    size:
                                        10

                                },


                                callback:
                                    function(
                                        value
                                    ) {

                                        return Number(
                                            value
                                        )
                                        .toLocaleString(
                                            "zh-CN"
                                        );

                                    }

                            }

                        }

                    }

                }

            }

        );


    setText(
        "chartCurrentPrice",
        formatNumber(
            data.close,
            2
        )
    );


    setText(
        "chartMa20",
        formatNumber(
            data.ma20,
            2
        )
    );


    setText(
        "chartMa60",
        formatNumber(
            data.ma60,
            2
        )
    );


    setText(
        "chartMa200",
        formatNumber(
            data.ma200,
            2
        )
    );

}


/* =========================================================
   FULL RENDER
   ========================================================= */

function renderCurrentIndex() {

    const data =
        getCurrentData();


    if (!data) {

        return;

    }


    if (
        data.error
    ) {

        setText(
            "coreConclusion",
            `行情数据获取失败：${data.error}`
        );


        return;

    }


    loadUserSettings();


    /* =====================================================
       INDEX INFO
       ===================================================== */

    setText(
        "indexName",
        data.name
        || "--"
    );


    setText(

        "indexSymbol",

        `${data.symbol || "--"} · ${data.date || "--"} · ${data.source || "--"}`

    );


    setText(
        "closePrice",
        formatNumber(
            data.close,
            2
        )
    );


    const change =
        safeNumber(
            data.change_pct,
            0
        );


    const changeElement =
        $("changePct");


    if (
        changeElement
    ) {

        changeElement.textContent =
            formatPercent(
                change,
                2
            );


        changeElement.className =
            "price-change";


        if (
            change > 0
        ) {

            changeElement.classList.add(
                "positive"
            );


        } else if (
            change < 0
        ) {

            changeElement.classList.add(
                "negative"
            );


        } else {

            changeElement.classList.add(
                "neutral"
            );

        }

    }


    /* =====================================================
       MODULES
       ===================================================== */

    renderValuationHero(
        data
    );


    renderValuationRange(
        data
    );


    renderRelativeValue(
        data
    );


    renderInvestmentPlan(
        data
    );


    renderValuationReasons(
        data
    );


    renderPricePosition(
        data
    );


    renderSentiment(
        data
    );


    renderTechnical(
        data
    );


    renderChart(
        data
    );


    renderScenario(
        data
    );


    renderMethodology(
        data
    );

}


/* =========================================================
   GUIDE
   ========================================================= */

function renderGuideDynamicText() {

    /*
       当前HTML主体说明已经完整，
       这里主要保留给后续后端guide扩展。
    */

}


/* =========================================================
   HELP CONTENT
   ========================================================= */

function getHelpContent(
    key
) {

    const backendGuide =
        marketData
        &&
        marketData.guide
        &&
        marketData.guide[
            key
        ];


    if (
        backendGuide
    ) {

        return {

            title:
                backendGuide.title
                || "指标说明",

            text:
                backendGuide.meaning
                || backendGuide.question
                || ""

        };

    }


    const fallback = {

        valuation: {

            title:
                "估值状态",

            text:
                (
                    "估值是整个Index Radar的最高决策层。"
                    +
                    "不同指数采用不同方法，估值决定定投、持有、暂停新增或再平衡。"
                )

        },


        pe: {

            title:
                "市盈率 PE",

            text:
                (
                    "PE反映市场价格相对于企业盈利的倍数。"
                    +
                    "不同指数盈利结构不同，因此不能用同一个绝对PE阈值机械比较。"
                )

        },


        earnings_yield: {

            title:
                "盈利收益率",

            text:
                (
                    "盈利收益率 E/P 约等于 1/PE。"
                    +
                    "在盈利相对稳定的指数中，盈利收益率越高，通常意味着单位盈利对应的价格越低。"
                )

        },


        pe_percentile: {

            title:
                "PE历史分位",

            text:
                (
                    "表示当前PE在指数自身可比历史中的位置。"
                    +
                    "例如20%分位意味着历史上大约只有20%的时期PE比当前更低。"
                )

        },


        dividend_yield: {

            title:
                "股息率",

            text:
                (
                    "股息率是指数长期回报来源之一。"
                    +
                    "对于标普500等博格框架，股息率与盈利增长、估值变化共同影响长期回报。"
                )

        },


        investment_formula: {

            title:
                "定期不定额",

            text:
                (
                    "低估区内，估值越低，投入金额越高。"
                    +
                    "盈利收益率法使用 Aₜ=A₀×(EYₜ/EY₀)ⁿ；"
                    +
                    "PE法使用 Aₜ=A₀×(PE₀/PEₜ)ⁿ。"
                    +
                    "n只代表资金放大程度，不改变估值结论。"
                )

        },


        technical: {

            title:
                "技术状态",

            text:
                (
                    "MA、RSI和MACD只描述短期市场走势。"
                    +
                    "它们不会因为没有出现所谓技术确认，而推迟已经满足估值条件的定投。"
                )

        },


        sentiment: {

            title:
                "市场风险情绪",

            text:
                (
                    "VIX、VXN或波动状态用于观察市场是否谨慎或亢奋。"
                    +
                    "恐慌不自动代表买入，亢奋也不自动代表卖出。"
                )

        },


        probability: {

            title:
                "短期历史情境",

            text:
                (
                    "统计历史相似市场状态之后20个交易日的结果。"
                    +
                    "它不是未来真实概率，也不参与估值、定投金额或卖出判断。"
                )

        }

    };


    return (

        fallback[
            key
        ]

        ||

        {
            title:
                "指标说明",

            text:
                ""
        }

    );

}


/* =========================================================
   GUIDE MODAL
   ========================================================= */

function openGuideModal() {

    const modal =
        $("guideModal");


    if (!modal) {

        return;

    }


    modal.classList.add(
        "open"
    );


    modal.setAttribute(
        "aria-hidden",
        "false"
    );


    document.body.classList.add(
        "modal-open"
    );

}


function closeGuideModal() {

    const modal =
        $("guideModal");


    if (!modal) {

        return;

    }


    modal.classList.remove(
        "open"
    );


    modal.setAttribute(
        "aria-hidden",
        "true"
    );


    document.body.classList.remove(
        "modal-open"
    );

}


/* =========================================================
   HELP POPOVER
   ========================================================= */

function openHelpPopover(
    button,
    key
) {

    const popover =
        $("helpPopover");


    if (!popover) {

        return;

    }


    activeHelpButton =
        button;


    const content =
        getHelpContent(
            key
        );


    setText(
        "helpPopoverTitle",
        content.title
    );


    setText(
        "helpPopoverText",
        content.text
    );


    popover.classList.add(
        "open"
    );


    popover.setAttribute(
        "aria-hidden",
        "false"
    );


    const rect =
        button.getBoundingClientRect();


    const width =
        320;


    const margin =
        14;


    let left =
        rect.left
        +
        rect.width / 2
        -
        width / 2;


    left =
        clamp(

            left,

            margin,

            window.innerWidth
            -
            width
            -
            margin

        );


    let top =
        rect.bottom
        +
        10;


    if (
        top + 190
        >
        window.innerHeight
    ) {

        top =
            rect.top
            -
            190;

    }


    popover.style.left =
        `${left}px`;


    popover.style.top =
        `${Math.max(
            14,
            top
        )}px`;

}


function closeHelpPopover() {

    const popover =
        $("helpPopover");


    if (!popover) {

        return;

    }


    popover.classList.remove(
        "open"
    );


    popover.setAttribute(
        "aria-hidden",
        "true"
    );


    activeHelpButton =
        null;

}


/* =========================================================
   INDEX TABS
   ========================================================= */

document
    .querySelectorAll(
        ".index-tab"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () => {

                    document
                        .querySelectorAll(
                            ".index-tab"
                        )
                        .forEach(

                            item => {

                                item.classList.remove(
                                    "active"
                                );

                            }

                        );


                    button.classList.add(
                        "active"
                    );


                    currentIndex =
                        button.dataset.index;


                    closeHelpPopover();


                    renderCurrentIndex();

                }

            );

        }

    );


/* =========================================================
   CHART RANGE
   ========================================================= */

document
    .querySelectorAll(
        ".range-button"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                () => {

                    document
                        .querySelectorAll(
                            ".range-button"
                        )
                        .forEach(

                            item => {

                                item.classList.remove(
                                    "active"
                                );

                            }

                        );


                    button.classList.add(
                        "active"
                    );


                    currentChartRange =
                        safeNumber(
                            button.dataset.range,
                            252
                        );


                    const data =
                        getCurrentData();


                    if (
                        data
                        &&
                        !data.error
                    ) {

                        renderChart(
                            data
                        );

                    }

                }

            );

        }

    );


/* =========================================================
   INVESTMENT INPUT EVENTS
   ========================================================= */

[
    "baseInvestmentInput",
    "maxInvestmentInput",
    "riskSelect"
]
.forEach(

    id => {

        const element =
            $(id);


        if (!element) {

            return;

        }


        const update =
            () => {

                saveUserSettings();

                updateRiskDescription();


                const data =
                    getCurrentData();


                if (
                    data
                    &&
                    !data.error
                ) {

                    renderInvestmentPlan(
                        data
                    );

                }

            };


        element.addEventListener(
            "input",
            update
        );


        element.addEventListener(
            "change",
            update
        );

    }

);


/* =========================================================
   GUIDE EVENTS
   ========================================================= */

if (
    $("guideButton")
) {

    $("guideButton")
        .addEventListener(

            "click",

            openGuideModal

        );

}


if (
    $("guideCloseButton")
) {

    $("guideCloseButton")
        .addEventListener(

            "click",

            closeGuideModal

        );

}


const guideBackdrop =
    document.querySelector(
        ".guide-backdrop"
    );


if (
    guideBackdrop
) {

    guideBackdrop
        .addEventListener(

            "click",

            closeGuideModal

        );

}


/* =========================================================
   HELP EVENTS
   ========================================================= */

document
    .querySelectorAll(
        ".help-dot"
    )
    .forEach(

        button => {

            button.addEventListener(

                "click",

                event => {

                    event.stopPropagation();


                    const key =
                        button.dataset.help;


                    if (
                        activeHelpButton === button
                        &&
                        $("helpPopover")
                        &&
                        $("helpPopover")
                            .classList
                            .contains(
                                "open"
                            )
                    ) {

                        closeHelpPopover();

                        return;

                    }


                    openHelpPopover(
                        button,
                        key
                    );

                }

            );

        }

    );


if (
    $("helpPopoverClose")
) {

    $("helpPopoverClose")
        .addEventListener(

            "click",

            closeHelpPopover

        );

}


/* =========================================================
   CLICK OUTSIDE
   ========================================================= */

document.addEventListener(

    "click",

    event => {

        const popover =
            $("helpPopover");


        if (
            !popover
            ||
            !popover
                .classList
                .contains(
                    "open"
                )
        ) {

            return;

        }


        if (
            popover.contains(
                event.target
            )
        ) {

            return;

        }


        if (
            event.target.closest(
                ".help-dot"
            )
        ) {

            return;

        }


        closeHelpPopover();

    }

);


/* =========================================================
   ESCAPE
   ========================================================= */

document.addEventListener(

    "keydown",

    event => {

        if (
            event.key === "Escape"
        ) {

            closeGuideModal();

            closeHelpPopover();

        }

    }

);


/* =========================================================
   WINDOW RESIZE
   ========================================================= */

window.addEventListener(

    "resize",

    () => {

        if (
            activeHelpButton
        ) {

            closeHelpPopover();

        }

    }

);


/* =========================================================
   START
   ========================================================= */

loadMarketData();


/* =========================================================
   AUTO REFRESH
   ========================================================= */

setInterval(

    loadMarketData,

    REFRESH_INTERVAL

);
