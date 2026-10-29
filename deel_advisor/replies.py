"""From a parsed query to the Telegram HTML the user reads.

This is where currency conversion meets the calculation: amounts are converted into each
country's currency on the way in, `calc` does the arithmetic, and the totals are formatted on
the way out. Everything the user typed is escaped; everything else is our own copy.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from deel_advisor import calc, freshness, i18n
from deel_advisor.catalog import Catalog
from deel_advisor.fx import Rates
from deel_advisor.i18n import Lang, t
from deel_advisor.models import Contribution, Country, Figure
from deel_advisor.money import format_money, format_rate, whole
from deel_advisor.parser import Query

# Weekends and ECB holidays leave the last set up to four days old; older than that is news.
FX_STALE_DAYS = 4
# The horizon the compare view and the "entity from N people" hint assume.
REFERENCE_MONTHS = 12


@dataclass(frozen=True, slots=True)
class Context:
    catalog: Catalog
    rates: Rates
    today: date


def _date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _money(lang: Lang, amount: Decimal, currency: str) -> str:
    return format_money(amount, currency, lang)


def country_name(lang: Lang, country: Country) -> str:
    return i18n.COUNTRY_NAMES[lang].get(country.code, country.country)


def contribution_name(lang: Lang, contribution: Contribution) -> str:
    return i18n.CONTRIBUTIONS[lang].get(contribution.id, contribution.name)


def figure_label(lang: Lang, key: str, *, capitalize: bool = False) -> str:
    label = i18n.FIGURES[lang].get(key) or i18n.FIGURES["en"].get(key) or key.replace("_", " ")
    return label[:1].upper() + label[1:] if capitalize else label


def figure_value(lang: Lang, figure: Figure) -> str:
    if figure.kind == "rate":
        text = format_rate(Decimal(figure.value), lang)
    elif figure.kind == "money" and figure.currency is not None:  # the schema requires both together
        amount = Decimal(figure.value)
        # An hourly minimum wage needs its cents; a ceiling of €8,450 does not.
        text = format_money(amount, figure.currency, lang, with_cents=amount != whole(amount))
    else:
        text = html.escape(figure.value)
    if figure.period:
        text += i18n.PERIODS[lang][figure.period]
    return text


def warnings(lang: Lang, country: Country, ctx: Context) -> list[str]:
    state = freshness.check(country, ctx.today)
    lines = []
    if state.outdated_year:
        lines.append(t(lang, "warn.year", year=country.year, current=ctx.today.year))
    if state.unchecked_days:
        lines.append(t(lang, "warn.unchecked", date=_date(country.official.checked_at)))
    for mismatch in state.mismatches:
        lines.append(
            t(
                lang,
                "warn.mismatch",
                label=figure_label(lang, mismatch.key),
                deel=figure_value(lang, mismatch.deel),
                official=figure_value(lang, mismatch.official),
                since=_date(mismatch.official.effective_from or country.effective_from),
                url=html.escape(str(mismatch.official.source), quote=True),
            )
        )
    return lines


def _fx_warning(lang: Lang, ctx: Context) -> list[str]:
    if (ctx.today - ctx.rates.day).days > FX_STALE_DAYS:
        return [t(lang, "warn.fx_old", date=_date(ctx.rates.day))]
    return []


def local_salary(query: Query, country: Country, rates: Rates) -> Decimal:
    if query.currency is None:
        return query.salary
    return rates.convert(query.salary, query.currency, country.currency)


def eor_fee(country: Country, ctx: Context) -> Decimal:
    eor = ctx.catalog.eor
    return ctx.rates.convert(eor.monthly_fee, eor.currency, country.currency)


def cost(lang: Lang, query: Query, ctx: Context) -> str:
    country = query.countries[0]
    salary = local_salary(query, country, ctx.rates)
    result = calc.employer_cost(country, salary)
    cur = country.currency

    out = [
        t(lang, "cost.header", flag=country.flag, country=country_name(lang, country),
          salary=_money(lang, result.annual_salary, cur)),
    ]  # fmt: skip
    if query.salary_was_monthly:
        input_cur = query.currency or cur
        out.append(t(lang, "cost.monthly_input", monthly=_money(lang, query.salary / 12, input_cur)))
    if query.currency and query.currency != cur:
        out.append(
            t(lang, "cost.converted", amount=_money(lang, query.salary, query.currency),
              date=_date(ctx.rates.day))
        )  # fmt: skip
    out += [
        "",
        t(lang, "cost.total", annual=_money(lang, result.total_annual, cur),
          monthly=_money(lang, result.total_monthly, cur)),
        t(lang, "cost.burden", amount=_money(lang, result.contributions_annual, cur),
          rate=format_rate(result.burden.quantize(Decimal("0.001")), lang)),
        "",
    ]  # fmt: skip
    for line in result.lines:
        c = line.contribution
        rate = ("~" if c.estimate else "") + format_rate(c.rate, lang)
        # A band (floor and cap: UK pension, Spanish solidarity tiers) being full is not news.
        capped = f", {t(lang, 'cost.capped')}" if line.capped and c.floor is None else ""
        out.append(f"• {contribution_name(lang, c)} {rate}{capped} — {_money(lang, line.annual, cur)}")
    out += ["", t(lang, "cost.footer", year=country.year, since=_date(country.effective_from))]
    if any(c.estimate for c in country.contributions):
        out.append(t(lang, "cost.estimate_note"))

    extra = []
    minimum = country.minimum_wage
    if minimum is not None and salary < minimum.annual:
        example = f"{country.country} {whole(query.salary)}/mo"
        extra.append(
            t(lang, "cost.below_min_wage", year=country.year, minimum=_money(lang, minimum.annual, cur),
              example=html.escape(example))
        )  # fmt: skip
    extra += warnings(lang, country, ctx) + _fx_warning(lang, ctx)
    if extra:
        out += ["", *extra]
    return "\n".join(out)


def _pays_off(lang: Lang, result: calc.Plan) -> list[str]:
    lines = []
    team = result.breakeven_people
    horizon = i18n.months(lang, result.months)
    if team is None:
        lines.append(t(lang, "plan.never_people"))
    elif team > result.people:
        lines.append(t(lang, "plan.pays_off_people", team=i18n.people_gen(lang, team), months=horizon))
    after = result.breakeven_months
    if after is None:
        if team is not None:
            lines.append(t(lang, "plan.never_months", team=i18n.people_gen(lang, result.people)))
    else:
        lines.append(
            t(lang, "plan.pays_off_months", team=i18n.people_gen(lang, result.people),
              months=i18n.months(lang, after))
        )  # fmt: skip
    return lines


def plan(lang: Lang, query: Query, ctx: Context) -> str:
    country = query.countries[0]
    cur = country.currency
    fee = eor_fee(country, ctx)
    result = calc.plan(country, local_salary(query, country, ctx.rates), fee, query.people, query.months)
    team, horizon = i18n.people_gen(lang, query.people), i18n.months(lang, query.months)

    out = [
        t(lang, "plan.header", flag=country.flag, country=country_name(lang, country),
          team=i18n.people(lang, query.people), salary=_money(lang, result.cost.annual_salary, cur),
          months=horizon),
        "",
        t(lang, "plan.eor", provider=html.escape(ctx.catalog.eor.provider),
          total=_money(lang, result.eor_total, cur)),
        "   " + t(lang, "plan.eor_detail", fee=_money(lang, fee, cur)),
        t(lang, "plan.entity", total=_money(lang, result.entity_total, cur)),
        "   " + t(lang, "plan.entity_detail", setup=_money(lang, result.entity.setup, cur),
                  fixed=_money(lang, result.entity.monthly_fixed, cur),
                  per_employee=_money(lang, result.entity.per_employee_monthly, cur)),
        t(lang, "plan.same", amount=_money(lang, result.employment, cur)),
        "",
    ]  # fmt: skip

    diff = whole(abs(result.entity_saving))
    if diff == 0:
        out.append(t(lang, "plan.even", team=team, months=horizon))
    else:
        key = "plan.entity_cheaper" if result.entity_saving > 0 else "plan.eor_cheaper"
        out.append(t(lang, key, team=team, months=horizon, diff=_money(lang, diff, cur)))
    out += _pays_off(lang, result)
    out += ["", t(lang, "plan.note")]
    extra = warnings(lang, country, ctx) + _fx_warning(lang, ctx)
    if extra:
        out += ["", *extra]
    return "\n".join(out)


def compare(lang: Lang, query: Query, ctx: Context) -> str:
    first, second = query.countries
    common = query.currency or first.currency
    totals = []
    out = [
        t(lang, "compare.header", a=country_name(lang, first), b=country_name(lang, second),
          salary=_money(lang, query.salary, common)),
        "",
    ]  # fmt: skip
    for country in (first, second):
        local = ctx.rates.convert(query.salary, common, country.currency)
        fee = eor_fee(country, ctx)
        result = calc.plan(country, local, fee, people=1, months=REFERENCE_MONTHS)
        total_common = ctx.rates.convert(result.cost.total_annual, country.currency, common)
        totals.append((country, total_common, result.cost.burden))
        out.append(
            t(lang, "compare.row", flag=country.flag, country=country_name(lang, country),
              total=_money(lang, total_common, common),
              rate=format_rate(result.cost.burden.quantize(Decimal("0.001")), lang))
        )  # fmt: skip
        if country.currency != common:
            out.append(
                "   " + t(lang, "compare.row_local", currency=country.currency,
                          total=_money(lang, result.cost.total_annual, country.currency))
            )  # fmt: skip
        fee_text = _money(lang, ctx.rates.convert(fee, country.currency, common), common)
        team = result.breakeven_people
        if team is None:
            out.append("   " + t(lang, "compare.row_never", fee=fee_text))
        else:
            out.append("   " + t(lang, "compare.row_eor", fee=fee_text, team=i18n.people_gen(lang, team)))

    (c1, total1, burden1), (c2, total2, burden2) = totals
    if whole(total1) != whole(total2):
        cheaper, diff = (c1, total2 - total1) if total1 < total2 else (c2, total1 - total2)
        rate = format_rate(abs(burden1 - burden2).quantize(Decimal("0.001")), lang)
        out += [
            "",
            t(lang, "compare.cheaper", country=country_name(lang, cheaper), diff=_money(lang, diff, common),
              rate=rate),
        ]  # fmt: skip
    if first.currency != common or second.currency != common or query.currency:
        out.append(t(lang, "compare.fx", date=_date(ctx.rates.day)))
    extra = warnings(lang, first, ctx) + warnings(lang, second, ctx) + _fx_warning(lang, ctx)
    if extra:
        out += ["", *extra]
    return "\n".join(out)


def _link(url: object, text: str) -> str:
    return f'<a href="{html.escape(str(url), quote=True)}">{html.escape(text)}</a>'


def _host(url: object) -> str:
    host = str(url).split("//", 1)[-1].split("/", 1)[0]
    return host.removeprefix("www.")


def sources(lang: Lang, country: Country, ctx: Context) -> str:
    cur = country.currency
    eor = ctx.catalog.eor
    out = [
        t(lang, "sources.header", flag=country.flag, country=country_name(lang, country)),
        "",
        t(lang, "sources.rates", year=country.year, since=_date(country.effective_from),
          checked=_date(country.official.checked_at)),
    ]  # fmt: skip
    for c in country.contributions:
        rate = ("~" if c.estimate else "") + format_rate(c.rate, lang)
        out.append(f"• {contribution_name(lang, c)} {rate} — {_link(c.source, _host(c.source))}")
    if country.minimum_wage is not None:
        mw = country.minimum_wage
        value = figure_value(lang, Figure(value=str(mw.amount), kind="money", currency=cur, period=mw.period))
        label = figure_label(lang, "minimum_wage", capitalize=True)
        out.append(f"• {label} {value} — {_link(mw.source, _host(mw.source))}")

    out += ["", t(lang, "sources.entity")]
    for item in (*country.entity.setup_cost, *country.entity.monthly_fixed):
        suffix = i18n.PERIODS[lang]["month"] if item in country.entity.monthly_fixed else ""
        out.append(
            f"• {html.escape(item.name)} {_money(lang, item.amount, cur)}{suffix} — "
            f"{_link(item.source, _host(item.source))}"
        )
    if country.entity.share_capital:
        out.append("• " + t(lang, "sources.capital", amount=_money(lang, country.entity.share_capital, cur)))

    guide = country.deel_guide
    out += [
        "",
        t(lang, "sources.eor", provider=html.escape(eor.provider),
          fee=_money(lang, eor.monthly_fee, eor.currency),
          url=html.escape(str(eor.source), quote=True), checked=_date(eor.checked_at)),
        t(lang, "sources.guide", url=html.escape(str(guide.url), quote=True),
          checked=_date(guide.checked_at)),
    ]  # fmt: skip
    bad = {m.key: m for m in freshness.mismatches(country)}
    for key in sorted(guide.figures.keys() & country.official.figures.keys()):
        label = figure_label(lang, key, capitalize=True)
        if key in bad:
            out.append(
                t(lang, "sources.guide_bad", label=label, deel=figure_value(lang, bad[key].deel),
                  official=figure_value(lang, bad[key].official))
            )  # fmt: skip
        else:
            out.append(t(lang, "sources.guide_ok", label=label, value=figure_value(lang, guide.figures[key])))
    out += ["", t(lang, "sources.fx", date=_date(ctx.rates.day))]
    return "\n".join(out)


def countries_list(lang: Lang, catalog: Catalog) -> str:
    names = ", ".join(f"{c.flag} {country_name(lang, c)}" for c in catalog.countries)
    return t(lang, "countries", list=names)
