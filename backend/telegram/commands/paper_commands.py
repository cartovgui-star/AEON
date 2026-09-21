"""
Paper Trading Command Handlers
"""
import logging

logger = logging.getLogger(__name__)

_ACCOUNT_ORDER = ['PRO', 'STARTER', 'REAL_LIFE', 'THE_PROOF', 'BENCHMARK', 'TIER_5K', 'TIER_1K', 'TIER_500']


def _cfg(account_id):
    from paper_trading import ACCOUNTS
    return ACCOUNTS.get(account_id, {})


def _fmt_money(v):
    return '$ {:,.2f}'.format(v or 0.0).replace('$ ', '$')


async def _get_all_summaries():
    import app_state
    pt = app_state.paper_trading
    if pt is None:
        raise RuntimeError('paper_trading not ready')
    accounts = await pt.get_all_accounts()
    ids = [a.get('_id') for a in accounts if a.get('_id')]
    ordered = [a for a in _ACCOUNT_ORDER if a in ids] + [a for a in ids if a not in _ACCOUNT_ORDER]
    out = []
    for acc_id in ordered:
        try:
            out.append(await pt.get_account_summary(acc_id))
        except Exception as e:
            logger.warning('account summary failed for %s: %s', acc_id, e)
    return out


def _render_account_block(summary, compact=False):
    account_id = summary.get('account_id', 'UNKNOWN')
    cfg = _cfg(account_id)
    emoji = summary.get('emoji') or cfg.get('emoji', '💼')
    name = summary.get('name') or cfg.get('name', account_id)
    bal = summary.get('balance', 0.0) or 0.0
    unreal = summary.get('unrealized_pnl', 0.0) or 0.0
    equity = bal + unreal
    positions = summary.get('open_positions', 0) or 0
    total_pnl = summary.get('total_pnl', 0.0) or 0.0
    wr = summary.get('win_rate', 0.0) or 0.0
    lev = cfg.get('max_leverage', '?')
    cap = cfg.get('daily_trade_cap', '?')
    pnl_icon = '🟢' if unreal >= 0 else '🔴'
    if compact:
        return '{} {}: bal {} | eq {} | open {} | lev {}x | cap {}/d'.format(emoji, account_id, _fmt_money(bal), _fmt_money(equity), positions, lev, cap)
    return '\n'.join([
        '{} {} ({})'.format(emoji, name, account_id),
        'Balance: {} | Equity: {}'.format(_fmt_money(bal), _fmt_money(equity)),
        'Open PnL: {} {} | Total PnL: {}'.format(pnl_icon, _fmt_money(unreal), _fmt_money(total_pnl)),
        'Open Positions: {} | Win Rate: {:.1f}%'.format(positions, wr),
        'Max Lev: {}x | Daily Cap: {}'.format(lev, cap),
    ])


async def handle_accounts(text, chat_id, context):
    try:
        summaries = await _get_all_summaries()
        if not summaries:
            return '📊 PAPER ACCOUNTS\n\nNo paper accounts found yet.', 'paper_trading'
        lines = ['📊 PAPER ACCOUNTS', '']
        total_open = 0
        total_bal = 0.0
        total_eq = 0.0
        for s in summaries:
            lines.append(_render_account_block(s, compact=True))
            total_open += s.get('open_positions', 0) or 0
            bal = s.get('balance', 0.0) or 0.0
            eq = bal + (s.get('unrealized_pnl', 0.0) or 0.0)
            total_bal += bal
            total_eq += eq
        lines.extend(['', 'Total Accounts: {} | Open Positions: {}'.format(len(summaries), total_open), 'Portfolio Balance: {} | Equity: {}'.format(_fmt_money(total_bal), _fmt_money(total_eq)), '', 'Use /pro, /starter, or /paper BTC for detail.'])
        return '\n'.join(lines), 'paper_trading'
    except Exception as e:
        logger.error('Error in /accounts: %s', e)
        return '❌ Error loading accounts: {}'.format(str(e)), 'paper_trading'


async def _handle_named_account(account_id):
    import app_state
    try:
        summary = await app_state.paper_trading.get_account_summary(account_id)
        if summary.get('error'):
            return '❌ {}'.format(summary['error']), 'paper_trading'
        lines = [_render_account_block(summary), '']
        positions = summary.get('positions', []) or []
        if positions:
            lines.append('Positions ({} open):'.format(len(positions)))
            for pos in positions[:6]:
                symbol = (pos.get('symbol') or '').replace('/USDT', '')
                direction = (pos.get('direction') or 'LONG').upper()
                entry = pos.get('entry_price', 0.0) or 0.0
                pnl = pos.get('unrealized_pnl', 0.0) or 0.0
                lev = pos.get('leverage', 1)
                size = pos.get('size_usd', 0.0) or 0.0
                dir_emoji = '🟢' if direction == 'LONG' else '🔴'
                lines.append('{} {} {} {}x | entry {} | size {} | pnl {}'.format(dir_emoji, symbol, direction, lev, _fmt_money(entry), _fmt_money(size), _fmt_money(pnl)))
        else:
            lines.append('No open positions.')
        return '\n'.join(lines), 'paper_trading'
    except Exception as e:
        logger.error('Error loading account %s: %s', account_id, e)
        return '❌ Error loading {}: {}'.format(account_id, str(e)), 'paper_trading'


async def handle_pro_account(text, chat_id, context):
    return await _handle_named_account('PRO')


async def handle_starter_account(text, chat_id, context):
    return await _handle_named_account('STARTER')


async def handle_real_life_account(text, chat_id, context):
    return await _handle_named_account('REAL_LIFE')


async def handle_the_proof_account(text, chat_id, context):
    return await _handle_named_account('THE_PROOF')


async def handle_benchmark_account(text, chat_id, context):
    return await _handle_named_account('BENCHMARK')


async def handle_tier5k_account(text, chat_id, context):
    return await _handle_named_account('TIER_5K')


async def handle_tier1k_account(text, chat_id, context):
    return await _handle_named_account('TIER_1K')


async def handle_tier500_account(text, chat_id, context):
    return await _handle_named_account('TIER_500')


async def handle_add_margin(text, chat_id, context):
    return '⚠️ /addmargin is legacy right now. Use the dashboard/operator flow until margin tooling is updated for the new account set.', 'paper_trading'


async def handle_paper_position(text, chat_id, context):
    parts = text.lower().split()
    if len(parts) < 2:
        return await handle_accounts(text, chat_id, context)
    symbol = parts[1].upper()
    if '/' not in symbol:
        symbol += '/USDT'
    try:
        summaries = await _get_all_summaries()
        lines = ['📊 PAPER POSITIONS: {}'.format(symbol), '']
        found = False
        for s in summaries:
            for pos in s.get('positions', []) or []:
                if pos.get('symbol') != symbol:
                    continue
                found = True
                direction = (pos.get('direction') or 'LONG').upper()
                dir_emoji = '🟢' if direction == 'LONG' else '🔴'
                lines.append('{} {} | {} {} {}x'.format(s.get('emoji', '💼'), s.get('account_id'), dir_emoji, direction, pos.get('leverage', 1)))
                lines.append('Entry: {} | Current: {}'.format(_fmt_money(pos.get('entry_price', 0.0) or 0.0), _fmt_money(pos.get('current_price', pos.get('entry_price', 0.0)) or 0.0)))
                lines.append('PnL: {} | Liq: {}'.format(_fmt_money(pos.get('unrealized_pnl', 0.0) or 0.0), _fmt_money(pos.get('liquidation_price', 0.0) or 0.0)))
                lines.append('')
        if not found:
            return 'No open paper positions for {}.'.format(symbol), 'paper_trading'
        return '\n'.join(lines).strip(), 'paper_trading'
    except Exception as e:
        logger.error('Error in /paper: %s', e)
        return '❌ Error loading positions: {}'.format(str(e)), 'paper_trading'


PAPER_HANDLERS = {
    '/accounts':   handle_accounts,
    '/pro':        handle_pro_account,
    '/starter':    handle_starter_account,
    '/reallife':   handle_real_life_account,
    '/real_life':  handle_real_life_account,
    '/theproof':   handle_the_proof_account,
    '/the_proof':  handle_the_proof_account,
    '/proof':      handle_the_proof_account,
    '/benchmark':  handle_benchmark_account,
    '/bm':         handle_benchmark_account,
    '/tier5k':     handle_tier5k_account,
    '/tier1k':     handle_tier1k_account,
    '/tier500':    handle_tier500_account,
    '/addmargin':  handle_add_margin,
    '/paper':      handle_paper_position,
}

_EXACT_HANDLERS = {
    '/accounts', '/pro', '/starter',
    '/reallife', '/real_life', '/theproof', '/the_proof', '/proof',
    '/benchmark', '/bm', '/tier5k', '/tier1k', '/tier500',
}


async def route_paper_command(text, chat_id, context):
    text_lower = text.lower().strip()
    if text_lower in _EXACT_HANDLERS:
        return await PAPER_HANDLERS[text_lower](text, chat_id, context)
    if text_lower.startswith('/addmargin'):
        return await handle_add_margin(text, chat_id, context)
    if text_lower.startswith('/paper'):
        return await handle_paper_position(text, chat_id, context)
    return None, None
