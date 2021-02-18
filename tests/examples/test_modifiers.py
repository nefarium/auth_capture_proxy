"""Test modifiers."""
from unittest.mock import patch

from yarl import URL
from bs4 import BeautifulSoup as bs
import authcaptureproxy.examples.modifiers as modifiers
from typing import Text
import random
import pytest


EMPTY_URL = URL("")
VALID_URL = URL("http://www.google.com")
RELATIVE_URL = URL("/test/asdf")
ABSOLUTE_URL = URL("http://example.com")

USERNAME = "TEST USER"
PASSWORD = "PASSWORD"  # nosec
FORM = """
<form>
  <label for="username">Name:</label><br>
  <input type="text" id="username" name="username"><br>
  <label for="password">Password:</label><br>
  <input type="password" id="password" name="password">
  <label for="description">Description:</label><br>
  <input type="text" id="description" name="description"><br>
</form>
"""

FORM_WITH_DATA = """
<form>
  <label for="username">Name:</label><br>
  <input type="text" id="username" name="username" value="Old Data"><br>
  <label for="password">Password:</label><br>
  <input type="password" id="password" name="password"value="Old Data" >
  <label for="description">Description:</label><br>
  <input type="text" id="description" name="description" value="Old Data"><br>
</form>
"""

FORM_NO_ID = """
<form>
  <label for="username">Name:</label><br>
  <input type="text" name="username"><br>
  <label for="password">Password:</label><br>
  <input type="password" name="password">
  <label for="description">Description:</label><br>
  <input type="text" name="description"><br>
</form>
"""
FORM_NO_NAME = """
<form>
  <label for="username">Name:</label><br>
  <input type="text" id="username" ><br>
  <label for="password">Password:</label><br>
  <input type="password" id="password" >
  <label for="description">Description:</label><br>
  <input type="text" id="description" ><br>
</form>
"""

FORM_WITH_EMPTY_ACTION = """
<form action="">
  <label for="username">Name:</label><br>
  <input type="text" id="username" name="username" value="Old Data"><br>
  <label for="password">Password:</label><br>
  <input type="password" id="password" name="password"value="Old Data" >
  <label for="description">Description:</label><br>
  <input type="text" id="description" name="description" value="Old Data"><br>
</form>
"""
AUTOFILL_DICT = {"username": USERNAME, "password": PASSWORD}

KNOWN_URLS_ATTRS = {
    "script": "src",
    "link": "href",
    "form": "action",
    "a": "href",
    "img": "src",
}

PROXY_URL = "https://www.proxy.com"
PROXY_URL_WITH_PATH = "https://www.proxy.com/oauth/path"
HOST_URL = "https://www.host.com"
HOST_URL_WITH_PATH = "https://www.host.com/auth/path/test?attr=asdf"
RELATIVE_URLS = ["asdf/asbklahef", "/root/asdf/b"]
ABSOLUTE_URLS = [PROXY_URL, PROXY_URL_WITH_PATH, HOST_URL_WITH_PATH]


def test_autofill():
    """Test autofill will modify html."""
    for form in [FORM, FORM_WITH_DATA, FORM_NO_NAME, FORM_NO_ID, build_random_html()]:
        result = modifiers.autofill(AUTOFILL_DICT, form)
        soup = bs(result, "html.parser")
        for tag in soup.findAll("input"):
            if tag.name in AUTOFILL_DICT:
                assert tag.value == AUTOFILL_DICT[tag.name]
            if tag.id in AUTOFILL_DICT:
                assert tag.value == AUTOFILL_DICT[tag.id]


def test_autofill_no_html():
    """Test autofill will return empty string if no input."""
    assert "" == modifiers.autofill(AUTOFILL_DICT, "")


def test_autofill_no_dict():
    """Test autofill will return unmodified if no dictionary."""
    for form in [FORM, FORM_WITH_DATA, FORM_NO_NAME, FORM_NO_ID, build_random_html()]:
        assert form == modifiers.autofill({}, form)


def build_random_html(size: int = 10, url: Text = HOST_URL_WITH_PATH) -> Text:
    """Builds random html."""

    soup = bs(FORM_WITH_DATA, "html.parser")
    for i in range(size):
        tag = random.choice(list(KNOWN_URLS_ATTRS))  # nosec
        attribute = KNOWN_URLS_ATTRS[tag]
        new_tag = soup.new_tag(tag, **{attribute: url})
        soup.append(new_tag)
    return str(soup)


@pytest.mark.asyncio
async def test_replace_matching_urls():
    """Test matching urls replaced."""
    for form in [FORM, FORM_WITH_DATA, FORM_NO_NAME, FORM_NO_ID, build_random_html()]:
        result = await modifiers.replace_matching_urls(HOST_URL, PROXY_URL, form)
        assert HOST_URL not in result
        if HOST_URL in form:
            assert str(URL(PROXY_URL).with_path(URL(HOST_URL_WITH_PATH).path)) in result


@pytest.mark.asyncio
async def test_replace_empty_action_urls():
    for form in [
        FORM,
        FORM_WITH_DATA,
        FORM_NO_NAME,
        FORM_NO_ID,
        build_random_html(),
        FORM_WITH_EMPTY_ACTION,
    ]:
        for url in [HOST_URL, HOST_URL_WITH_PATH, PROXY_URL, PROXY_URL_WITH_PATH]:
            result = await modifiers.replace_empty_action_urls(url, form)
            old_soup = bs(form, "html.parser")
            soup = bs(result, "html.parser")
            if old_soup.find("form", action="").get("action") is not None:
                assert not soup.find("form", action="")
                assert soup.find("form", action=url)["action"] == url


@pytest.mark.asyncio
async def test_prepend_relative_urls():
    start_url = random.choice(RELATIVE_URLS)  # nosec
    for form in [
        FORM,
        FORM_WITH_DATA,
        FORM_NO_NAME,
        FORM_NO_ID,
        build_random_html(url=start_url),
        FORM_WITH_EMPTY_ACTION,
    ]:
        for url in [HOST_URL, HOST_URL_WITH_PATH, PROXY_URL, PROXY_URL_WITH_PATH]:
            result = await modifiers.prepend_relative_urls(url, form)
            old_soup = bs(form, "html.parser")
            soup = bs(result, "html.parser")
            for tag, attribute in KNOWN_URLS_ATTRS.items():
                if old_soup.find(tag) and old_soup.find(tag).get(attribute) is not None:
                    old_url = old_soup.find(tag).get(attribute)
                    new_url = soup.find(tag).get(attribute)
                    if URL(old_url).is_absolute():
                        assert new_url != old_url
                        assert start_url == old_url
                    else:
                        assert URL(new_url).is_absolute()
                        assert new_url.startswith(str(URL(url).with_query({})))
                        if old_url:
                            assert new_url.endswith(start_url)
