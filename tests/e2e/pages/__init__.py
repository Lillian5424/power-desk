"""Page objects: the only place in the suite that knows how the UI is built.

If a label or test id changes, you fix it here once, not in every test.
"""

from .blotter_page import BlotterPage
from .dashboard_page import DashboardPage
from .login_page import LoginPage
from .positions_page import PositionsPage
from .trade_ticket_page import TradeTicketPage

__all__ = ["BlotterPage", "DashboardPage", "LoginPage", "PositionsPage", "TradeTicketPage"]
