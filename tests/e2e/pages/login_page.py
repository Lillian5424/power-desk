from __future__ import annotations

from playwright.sync_api import Page

from .base_page import BasePage


class LoginPage(BasePage):
    path = "/login"

    def __init__(self, page: Page):
        super().__init__(page)
        self.username = page.get_by_label("Username")
        self.password = page.get_by_label("Password")
        self.submit = page.get_by_role("button", name="Sign in")
        self.error = page.get_by_test_id("login-error")

    def login(self, username: str, password: str) -> None:
        self.username.fill(username)
        self.password.fill(password)
        self.submit.click()
