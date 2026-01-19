from selenium.webdriver.remote.webdriver import WebDriver
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


# Converts a chess character into an int
# Examples: a -> 1, b -> 2, h -> 8, etc.
def char_to_num(char):
    return ord(char) - ord("a") + 1


# Attaches to a running webdriver
# Returns the webdriver
# Updated for Selenium 4.x compatibility
def attach_to_session(executor_url, session_id):
    original_execute = WebDriver.execute

    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response - Selenium 4.x expects this format
            return {'value': {'sessionId': session_id, 'capabilities': {}}}
        else:
            return original_execute(self, command, params)

    # Patch the function before creating the driver object
    WebDriver.execute = new_command_execute

    # Create driver with options instead of deprecated desired_capabilities
    options = Options()
    driver = webdriver.Remote(command_executor=executor_url, options=options)
    driver.session_id = session_id

    # Replace the patched function with original function
    WebDriver.execute = original_execute

    return driver
