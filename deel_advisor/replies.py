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
from deel_advisor.parser import MAX_MONTHS, Query

# Weekends and ECB holidays leave the last set up to four days old; older than that is news.
FX_STALE_DAYS = 4
# The horizon the compare view and the "entity from N people" hint assume.
REFERENCE_MONTHS = 12


@dataclass(frozen=True, slots=True)
class Context:
    catalog: Catalog
    rates: Rates
    today: date


_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _date(value: date, lang: Lang) -> str:
    """29 Oct 2026 in English (no day/month ambiguity), 29/10/2026 in Spanish, 29.10.2026 elsewhere."""
    if lang == "en":
        return f"{value.day} {_MONTH_ABBR[value.month - 1]} {value.year}"
    return value.strftime("%d/%m/%Y" if lang == "es" else "%d.%m.%Y")


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
        lines.append(t(lang, "warn.unchecked", date=_date(country.official.checked_at, lang)))
    for mismatch in state.mismatches:
        lines.append(
            t(
                lang,
                "warn.mismatch",
                label=figure_label(lang, mismatch.key),
                deel=figure_value(lang, mismatch.deel),
                official=figure_value(lang, mismatch.official),
                since=_date(mismatch.official.effective_from or country.effective_from, lang),
                url=html.escape(str(mismatch.official.source), quote=True),
            )
        )
    return lines


def _fx_warning(lang: Lang, ctx: Context) -> list[str]:
    if (ctx.today - ctx.rates.day).days > FX_STALE_DAYS:
        return [t(lang, "warn.fx_old", date=_date(ctx.rates.day, lang))]
    return []


def local_salary(query: Query, country: Country, rates: Rates) -> Decimal:
    if query.currency is None:
        return query.salary
    return rates.convert(query.salary, query.currency, country.currency)


def payroll_fee(country: Country, ctx: Context) -> Decimal | None:
    """Deel Payroll's price per person in the country's currency, if the data has one."""
    payroll = ctx.catalog.eor.payroll
    if payroll is None:
        return None
    return ctx.rates.convert(payroll.monthly_fee, payroll.currency, country.currency)


def eor_fee(country: Country, ctx: Context) -> Decimal:
    eor = ctx.catalog.eor
    return ctx.rates.convert(eor.monthly_fee, eor.currency, country.currency)


def _input_lines(lang: Lang, query: Query, country: Country, ctx: Context) -> list[str]:
    """How the typed salary became the one in the header: monthly × 12, and the FX rate used."""
    lines = []
    if query.salary_was_monthly:
        monthly = _money(lang, query.salary / 12, query.currency or country.currency)
        lines.append(t(lang, "cost.monthly_input", monthly=monthly))
    if query.currency and query.currency != country.currency:
        amount = _money(lang, query.salary, query.currency)
        lines.append(t(lang, "cost.converted", amount=amount, date=_date(ctx.rates.day, lang)))
    return lines


CEILING_FIGURES = ("pension_cap", "health_cap", "max_insurable_income")


def _ceiling_changed(country: Country) -> date | None:
    """When a ceiling moved during the year (Bulgaria, 1 August), the date of the newer one.

    The calculation prices a hire made from now on, so every month uses the newest ceiling
    rather than averaging in months that are already behind us; the reply says so.
    """
    dates = [
        figure.effective_from
        for key, figure in country.official.figures.items()
        if key in CEILING_FIGURES and figure.effective_from and figure.effective_from > country.effective_from
    ]
    return max(dates, default=None)


def cost(lang: Lang, query: Query, ctx: Context) -> str:
    country = query.countries[0]
    salary = local_salary(query, country, ctx.rates)
    result = calc.employer_cost(country, salary)
    cur = country.currency

    out = [
        t(lang, "cost.header", flag=country.flag, country=country_name(lang, country),
          salary=_money(lang, result.annual_salary, cur)),
    ]  # fmt: skip
    out += _input_lines(lang, query, country, ctx)
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
    out += ["", t(lang, "cost.footer", year=country.year, since=_date(country.effective_from, lang))]
    if (cap_since := _ceiling_changed(country)) is not None:
        out.append(t(lang, "cost.cap_since", date=_date(cap_since, lang)))
    if any(c.estimate for c in country.contributions):
        out.append(t(lang, "cost.estimate_note"))

    extra = []
    minimum = country.minimum_wage
    if minimum is not None and salary < minimum.annual:
        warning = t(lang, "cost.below_min_wage", year=country.year, minimum=_money(lang, minimum.annual, cur))
        if not query.salary_was_monthly:
            # They probably typed a monthly figure: offer exactly that back, currency included.
            currency = f" {query.currency}" if query.currency else ""
            example = f"{country.country} {whole(query.salary)}{currency}/mo"
            warning += " " + t(lang, "cost.monthly_hint", example=html.escape(example))
        extra.append(warning)
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
        lines.append(t(lang, "plan.pays_off_people", team=i18n.people_for(lang, team), months=horizon))
    after = result.breakeven_months
    if after is not None and after > MAX_MONTHS:
        after = None  # "pays off after 234 years" is a never, not a plan
    if after is None:
        if team is not None:
            lines.append(t(lang, "plan.never_months", team=i18n.people_for(lang, result.people)))
    else:
        lines.append(
            t(lang, "plan.pays_off_months", team=i18n.people_for(lang, result.people),
              months=i18n.months_after(lang, after))
        )  # fmt: skip
    return lines


def plan(lang: Lang, query: Query, ctx: Context) -> str:
    country = query.countries[0]
    cur = country.currency
    fee = eor_fee(country, ctx)
    payroll = payroll_fee(country, ctx)
    result = calc.plan(country, local_salary(query, country, ctx.rates), fee, query.people, query.months, payroll)
    team, horizon = i18n.people_for(lang, query.people), i18n.months(lang, query.months)
    eor = ctx.catalog.eor
    entity = result.entity
    fee_source = ""
    if eor.currency != cur:
        list_price = _money(lang, eor.monthly_fee, eor.currency)
        fee_source = " " + t(lang, "plan.eor_fx", price=list_price, date=_date(ctx.rates.day, lang))

    out = [
        t(lang, "plan.header", flag=country.flag, country=country_name(lang, country),
          team=i18n.people(lang, query.people), salary=_money(lang, result.cost.annual_salary, cur),
          months=horizon),
        *_input_lines(lang, query, country, ctx),
        "",
        t(lang, "plan.eor", provider=html.escape(eor.provider), total=_money(lang, result.eor_total, cur)),
        "   " + t(lang, "plan.eor_detail", fee=_money(lang, fee, cur)) + fee_source,
        t(lang, "plan.entity_deel" if payroll is not None else "plan.entity",
          total=_money(lang, result.entity_total, cur)),
        "   " + t(lang, "plan.entity_detail", setup=_money(lang, entity.setup, cur),
                  exit=_money(lang, entity.exit, cur), fixed=_money(lang, entity.monthly_fixed, cur),
                  per_employee=_money(lang, entity.per_employee_monthly, cur)),
    ]  # fmt: skip
    if result.bridge_months:
        out.append(
            "   " + t(lang, "plan.entity_bridge", weeks=i18n.weeks(lang, country.entity.setup_time.weeks),
                      amount=_money(lang, result.bridge_fees, cur))
        )  # fmt: skip
    out += [t(lang, "plan.same", amount=_money(lang, result.employment, cur)), ""]

    diff = whole(abs(result.entity_saving))
    if diff == 0:
        out.append(t(lang, "plan.even", team=team, months=horizon))
    else:
        key = "plan.entity_cheaper" if result.entity_saving > 0 else "plan.eor_cheaper"
        out.append(t(lang, key, team=team, months=horizon, diff=_money(lang, diff, cur)))
    out += _pays_off(lang, result)
    if result.entity_saving > 0 and payroll is not None:
        out.append(t(lang, "plan.switch", fee=_money(lang, payroll, cur)))
    out += ["", t(lang, "plan.note")]
    if (cap_since := _ceiling_changed(country)) is not None:
        out.append(t(lang, "cost.cap_since", date=_date(cap_since, lang)))
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
        result = calc.plan(country, local, fee, people=1, months=REFERENCE_MONTHS,
                           payroll_fee=payroll_fee(country, ctx))  # fmt: skip
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
            out.append("   " + t(lang, "compare.row_eor", fee=fee_text, team=i18n.people_for(lang, team)))

    (c1, total1, _), (c2, total2, _) = totals
    if whole(total1) != whole(total2):
        cheaper, diff = (c1, total2 - total1) if total1 < total2 else (c2, total1 - total2)
        # Share of the dearer country's total, not a difference of contribution rates.
        rate = format_rate((diff / max(total1, total2)).quantize(Decimal("0.001")), lang)
        out += [
            "",
            t(lang, "compare.cheaper", country=country_name(lang, cheaper), diff=_money(lang, diff, common),
              rate=rate),
        ]  # fmt: skip
    if first.currency != common or second.currency != common or query.currency:
        out.append(t(lang, "compare.fx", date=_date(ctx.rates.day, lang)))
    extra = warnings(lang, first, ctx) + warnings(lang, second, ctx) + _fx_warning(lang, ctx)
    if extra:
        out += ["", *extra]
    return "\n".join(out)


def team(lang: Lang, query: Query, ctx: Context) -> str:
    """A team spread over several countries: EOR fees against one entity per country.

    Salary and contributions are the same either way, so only the overhead is compared, in the
    currency the salary was typed in (EUR by default).
    """
    common = query.currency or "EUR"
    notes: list[str] = []
    # One line for the guides, not one per figure: the per-figure detail is in /plan and /sources.
    outdated_guides: list[str] = []
    out = [
        t(lang, "team.header", countries=len(query.countries), team=i18n.people(lang, query.people),
          salary=_money(lang, query.salary, common), months=i18n.months(lang, query.months)),
        "",
    ]  # fmt: skip
    total_eor = total_entity = employment = best = Decimal(0)
    breakevens: list[str] = []
    on_eor: list[str] = []
    on_entity: list[str] = []
    for country, count in zip(query.countries, query.counts, strict=True):
        local = ctx.rates.convert(query.salary, common, country.currency)
        result = calc.plan(country, local, eor_fee(country, ctx), count, query.months, payroll_fee(country, ctx))
        minimum = country.minimum_wage
        if minimum is not None and local < minimum.annual:
            notes.append(f"{country.flag} " + t(lang, "cost.below_min_wage", year=country.year,
                                                  minimum=_money(lang, minimum.annual, country.currency)))  # fmt: skip
        state = freshness.check(country, ctx.today)
        if state.mismatches:
            outdated_guides.append(country.flag)
        if state.outdated_year:
            notes.append(f"{country.flag} " + t(lang, "warn.year", year=country.year, current=ctx.today.year))
        if state.unchecked_days:
            notes.append(f"{country.flag} " + t(lang, "warn.unchecked", date=_date(country.official.checked_at, lang)))
        eor = ctx.rates.convert(result.eor_fees, country.currency, common)
        entity = ctx.rates.convert(result.entity_overhead, country.currency, common)
        total_eor += eor
        total_entity += entity
        employment += ctx.rates.convert(result.employment, country.currency, common)
        best += min(eor, entity)
        (on_eor if eor <= entity else on_entity).append(country.flag)
        key = "team.row_eor" if eor <= entity else "team.row_entity"
        out.append(
            t(lang, key, flag=country.flag, country=country_name(lang, country), count=count,
              eor=_money(lang, eor, common), entity=_money(lang, entity, common))
        )  # fmt: skip
        team_size = result.breakeven_people
        breakevens.append(f"{country.flag} {team_size}" if team_size is not None else f"{country.flag} —")

    entities = len(query.countries)
    out += [
        "",
        t(lang, "team.total", eor=_money(lang, total_eor, common), entities=entities,
          entity=_money(lang, total_entity, common)),
    ]  # fmt: skip
    diff = whole(abs(total_entity - total_eor))
    if diff == 0:
        out.append(t(lang, "plan.even", team=i18n.people_for(lang, query.people),
                     months=i18n.months(lang, query.months)))  # fmt: skip
    elif total_eor < total_entity:
        out.append(t(lang, "team.eor_saves", months=i18n.months(lang, query.months),
                     diff=_money(lang, diff, common), entities=entities))  # fmt: skip
    else:
        out.append(t(lang, "team.entities_win", months=i18n.months(lang, query.months),
                     diff=_money(lang, diff, common)))  # fmt: skip
    if on_eor and on_entity:
        # Each country on its own cheaper side beats both all-EOR and all-entities.
        out.append(t(lang, "team.mix", eor=" ".join(on_eor), entity=" ".join(on_entity),
                     total=_money(lang, best, common)))  # fmt: skip
    out += [
        t(lang, "team.breakeven", list=" · ".join(breakevens), months=i18n.months(lang, query.months)),
        t(lang, "team.same", amount=_money(lang, employment, common)),
        "",
        t(lang, "plan.note"),
    ]
    # The EOR fee is a USD list price, so a conversion is always involved.
    out.append(t(lang, "compare.fx", date=_date(ctx.rates.day, lang)))
    if outdated_guides:
        notes.append(t(lang, "team.guides", flags=" ".join(outdated_guides)))
    notes += _fx_warning(lang, ctx)
    if notes:
        out += ["", *notes]
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
        t(lang, "sources.rates", year=country.year, since=_date(country.effective_from, lang),
          checked=_date(country.official.checked_at, lang)),
    ]  # fmt: skip
    for c in country.contributions:
        rate = ("~" if c.estimate else "") + format_rate(c.rate, lang)
        local = f" ({html.escape(c.local_name)})" if c.local_name else ""
        out.append(f"• {contribution_name(lang, c)}{local} {rate} — {_link(c.source, _host(c.source))}")
    if country.minimum_wage is not None:
        mw = country.minimum_wage
        value = figure_value(lang, Figure(value=str(mw.amount), kind="money", currency=cur, period=mw.period))
        label = figure_label(lang, "minimum_wage", capitalize=True)
        out.append(f"• {label} {value} — {_link(mw.source, _host(mw.source))}")

    out += ["", t(lang, "sources.entity")]
    for item in (*country.entity.setup_cost, *country.entity.monthly_fixed):
        amount = format_money(item.amount, cur, lang, with_cents=item.amount != whole(item.amount))
        if item in country.entity.monthly_fixed:
            amount += t(lang, "sources.per_person") if item.per_employee else i18n.PERIODS[lang]["month"]
        if item.payroll and eor.payroll is not None:
            amount += f" ({t(lang, 'sources.replaced')})"
        official = f" · {t(lang, 'sources.official')}" if item.kind == "official" else ""
        out.append(f"• {html.escape(item.name)} {amount}{official} — {_link(item.source, _host(item.source))}")
    setup_time, exit_items = country.entity.setup_time, country.entity.exit_cost
    weeks = i18n.weeks(lang, setup_time.weeks)
    out.append(f"• {t(lang, 'sources.setup_time', weeks=weeks)} — {_link(setup_time.source, _host(setup_time.source))}")
    for item in exit_items:
        amount = format_money(item.amount, cur, lang, with_cents=item.amount != whole(item.amount))
        out.append(f"• {t(lang, 'sources.exit')} {html.escape(item.name)} {amount} — "
                   f"{_link(item.source, _host(item.source))}")  # fmt: skip
    capital = country.entity.share_capital
    if capital is not None:
        line = t(lang, "sources.capital", amount=_money(lang, capital.amount, cur))
        out.append(f"• {line} — {_link(capital.source, _host(capital.source))}")

    guide = country.deel_guide
    out += [
        "",
        t(lang, "sources.eor", provider=html.escape(eor.provider),
          fee=_money(lang, eor.monthly_fee, eor.currency),
          url=html.escape(str(eor.source), quote=True), checked=_date(eor.checked_at, lang)),
    ]  # fmt: skip
    if eor.payroll is not None:
        out.append(
            t(lang, "sources.payroll", fee=_money(lang, eor.payroll.monthly_fee, eor.payroll.currency),
              url=html.escape(str(eor.payroll.source), quote=True), checked=_date(eor.payroll.checked_at, lang))
        )  # fmt: skip
    out.append(t(lang, "sources.guide", url=html.escape(str(guide.url), quote=True),
                 checked=_date(guide.checked_at, lang)))  # fmt: skip
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
    notes = [*country.notes, *country.entity.notes]
    if notes:
        out += ["", t(lang, "sources.notes"), *(f"• {html.escape(note)}" for note in notes)]
    out += ["", t(lang, "sources.fx", date=_date(ctx.rates.day, lang))]
    return "\n".join(out)


def countries_list(lang: Lang, catalog: Catalog) -> str:
    names = ", ".join(f"{c.flag} {country_name(lang, c)}" for c in catalog.countries)
    return t(lang, "countries", list=names)
