"""
Help & General Command Handlers
"""
import logging

logger = logging.getLogger(__name__)

HELP_TEXT = '''🤖 AEON OPERATOR COMMANDS

📊 MARKET
• /market — Global market summary
• /price [coin] — Live price
• /scan [coin] — Deep scan
• /quant [coin] — Quant report

💼 PAPER ACCOUNTS
• /accounts — All accounts snapshot
• /pro /starter /reallife /proof /benchmark — Account detail
• /tier5k /tier1k /tier500 — Tier account detail
• /paper [coin] — Open positions by symbol

🧠 FW_V2 + GOVERNANCE
• /fw or /fwv2 — FW_V2 operator report
• /governance or /gov — All engine governance states
• /status — System + feed + governance snapshot

🔧 ENGINES
• /engines — All 9 engines with governance
• /engine [name] on/off — Toggle engine

📈 STATS (live paper_trades)
• /stats — 7d/30d performance
• /accuracy /acc — Accuracy by direction + engine
• /leaderboard /lb — Top coins by PnL

📊 LIVE CHART ANALYSIS
• /chart [coin] [tf] — Full TA on any coin (e.g. /chart BTC 4h)
• /watch — Chart scanner status + watchlist

⚙️ INFO
• /ping — Bot health check
• /settings — Your preferences
• /help — This menu'''


def _fmt_pct(v):
    return 'n/a' if v is None else '{:+.2f}%'.format(v)


async def handle_help(text, chat_id, context):
    return HELP_TEXT, 'help'


async def handle_start(text, chat_id, context):
    response = '''👋 Welcome to AEON.

This bot now reflects the governed paper-trading stack:
• live paper accounts
• engine governance
• cohort-aware FW_V2 monitoring
• cleaner operator snapshots

Start with:
• /status
• /accounts
• /fw
• /help'''
    return response, 'general'


async def handle_ping(text, chat_id, context):
    from datetime import datetime, timezone
    from feed_health import feed_health
    now = datetime.now(timezone.utc)
    response = '🏓 PONG!\n\nBot: 🟢 Online\n{}\nTime: {}'.format(feed_health.status_line(), now.strftime('%Y-%m-%d %H:%M:%S UTC'))
    return response, 'general'


async def handle_status(text, chat_id, context):
    import app_state
    from feed_health import feed_health
    from engine_health import EngineHealthScorer
    try:
        lines = ['📊 AEON STATUS', '', '📡 Feeds: {}'.format(feed_health.status_line())]
        paper = app_state.paper_trading
        if paper is not None:
            accounts = await paper.get_all_accounts()
            total_open = 0
            for acc in accounts:
                total_open += len([p for p in acc.get('positions', []) if p.get('status') == 'open'])
            lines.append('💼 Paper Accounts: {} | Open Positions: {}'.format(len(accounts), total_open))
        else:
            lines.append('💼 Paper Accounts: not ready')
        if app_state.db is not None:
            gov_docs = await app_state.db.engine_governance.find({}, {'_id': 0, 'engine': 1, 'recommendation': 1}).to_list(length=100)
            if gov_docs:
                restricted = [g['engine'] for g in gov_docs if g.get('recommendation') in ('restricted', 'sandbox_only', 'disable_candidate')]
                monitor = [g['engine'] for g in gov_docs if g.get('recommendation') == 'monitor']
                lines.append('🧠 Governance: {} tracked | monitor {} | restricted/sandbox {}'.format(len(gov_docs), len(monitor), len(restricted)))
            scorer = EngineHealthScorer()
            fw = await scorer.compute_one(app_state.db, 'FREE_WILL_V2', days=7)
            gov = await app_state.db.engine_governance.find_one({'engine': 'FREE_WILL_V2'}) or {}
            malformed_rejects = await app_state.db.trade_candidates.count_documents({'engine': 'FREE_WILL_V2', 'route_results.outcome_type': 'malformed_stop'})
            lines.extend(['', '🧠 FW_V2: tier {} | score {:.2f} | cohorts {}'.format(fw.tier, fw.score, fw.n_cohorts), 'Gov: {} | D-weeks: {} | malformed rejects: {}'.format(gov.get('recommendation', 'n/a'), gov.get('consecutive_d_weeks', 0), malformed_rejects)])
        return '\n'.join(lines), 'general'
    except Exception as e:
        logger.error('Error getting status: %s', e)
        return '❌ Error getting status: {}'.format(str(e)), 'general'


async def handle_fw_report(text, chat_id, context):
    try:
        from routes.dashboard import fw_v2_operator_report
        report = await fw_v2_operator_report()
        if isinstance(report, dict) and report.get('error'):
            return '❌ FW report error: {}'.format(report['error']), 'general'
        h = report.get('health_7d', {})
        g = report.get('governance', {})
        rp = report.get('rolling_performance', {})
        lp = report.get('leverage_pipeline', {})
        lines = [
            '🧠 FREE_WILL_V2',
            'Status: {}'.format(report.get('status', 'n/a')),
            'Score: {:.2f} | Tier: {}'.format(h.get('score', 0) or 0, h.get('tier', 'n/a')),
            'n_clean: {} | n_cohorts: {} | shrink: {:.3f}'.format(h.get('n_clean', 0) or 0, h.get('n_cohorts', 0) or 0, h.get('shrinkage_factor', 0) or 0),
            'Malformed trades: {} | malformed rejects 30d: {}'.format(h.get('malformed_trades', 0) or 0, lp.get('malformed_stop_rejects_30d', 0) or 0),
            'Governance: {} | D-weeks: {}'.format(g.get('recommendation', 'n/a'), g.get('consecutive_d_weeks', 0)),
        ]
        for key in ('7d', '14d', '30d'):
            row = rp.get(key, {})
            lines.append('{}: WR {} | EXP {} | PF {}'.format(key, row.get('win_rate_pct', 'n/a'), _fmt_pct(row.get('expectancy_pct')), row.get('profit_factor', 'n/a')))
        return '\n'.join(lines), 'general'
    except Exception as e:
        logger.error('Error in /fw: %s', e)
        return '❌ Error loading FW_V2 report: {}'.format(str(e)), 'general'


async def handle_settings(text, chat_id, context):
    import app_state
    try:
        user_settings = await app_state.get_user_settings(chat_id)
        voice = user_settings.get('voice_enabled', False)
        alerts = user_settings.get('alerts_enabled', True)
        model = user_settings.get('model', 'claude')
        response = '⚙️ YOUR SETTINGS\n\n🔔 Alerts: {}\n🎤 Voice: {}\n🤖 AI Model: {}\n\nChange with:\n• /alerts [on/off]\n• /voice [on/off]\n• /claude or /gemini'.format('ON' if alerts else 'OFF', 'ON' if voice else 'OFF', str(model).upper())
    except Exception as e:
        response = '❌ Error getting settings: {}'.format(str(e))
    return response, 'settings'


async def handle_menu(text, chat_id, context):
    response = '📱 QUICK MENU\n\n1️⃣ /status — system snapshot\n2️⃣ /accounts — live paper accounts\n3️⃣ /fw — FW_V2 operator report\n4️⃣ /market — market overview\n5️⃣ /paper BTC — open BTC paper positions\n6️⃣ /help — full command list'
    return response, 'general'


GENERAL_HANDLERS = {
    '/help': handle_help,
    '/start': handle_start,
    '/ping': handle_ping,
    '/status': handle_status,
    '/fw': handle_fw_report,
    '/fwv2': handle_fw_report,
    '/settings': handle_settings,
    '/menu': handle_menu,
    '/commands': handle_help,
}


async def route_general_command(text, chat_id, context):
    text_lower = text.lower().strip()
    handler = GENERAL_HANDLERS.get(text_lower)
    if handler:
        return await handler(text, chat_id, context)
    return None
