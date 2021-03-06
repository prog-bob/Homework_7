import pytest
import requests
import allure
import time
import json

from selenium import webdriver


@allure.step("Waiting for resource availability {url}")
def url_data(url, timeout=10):
    while timeout:
        response = requests.get(url)
        if not response.ok:
            time.sleep(1)
            timeout -= 1
        else:
            if 'video' in url:
                return response.content
            else:
                return response.text
    return None


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
# https://github.com/pytest-dev/pytest/issues/230#issuecomment-402580536
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.outcome != 'passed':
        item.status = 'failed'
    else:
        item.status = 'passed'


def pytest_addoption(parser):
    parser.addoption("--browser", default="chrome")
    parser.addoption("--executor", default="127.0.0.1")
    parser.addoption("--bversion", action="store", default="87.0")
    parser.addoption("--vnc", action="store_true", default=False)
    parser.addoption("--logs", action="store_true", default=False)
    parser.addoption("--video", action="store_true", default=True)


@pytest.fixture
def remote_browser(request):
    browser = request.config.getoption("--browser")
    vnc = request.config.getoption("--vnc")
    logs = request.config.getoption("--logs")
    video = request.config.getoption("--video")
    version = request.config.getoption("--bversion")
    executor = request.config.getoption('--executor')
    executor_url = f"http://{executor}:4444/wd/hub"

    caps = {
        "browserName": browser,
        "browserVersion": version,
        "selenoid:options": {
            "enableVNC": vnc,
            "enableVideo": video,
            "enableLog": logs
        },
        "name": "QAPython"
    }

    driver = webdriver.Remote(
        desired_capabilities=caps,
        command_executor=executor_url
    )

    # Attach browser data
    allure.attach(
        name=driver.session_id,
        body=json.dumps(driver.desired_capabilities),
        attachment_type=allure.attachment_type.JSON)

    def finalizer():
        log_url = f"{executor}/logs/{driver.session_id}.log"
        video_url = f"http://{executor}:8080/video/{driver.session_id}.mp4"
        driver.quit()

        if request.node.status != 'passed':
            if logs:
                allure.attach(
                    name="selenoid_log_" + driver.session_id,
                    body=url_data(log_url),
                    attachment_type=allure.attachment_type.TEXT)
            if video:
                allure.attach(
                    body=url_data(video_url),
                    name="video_for_" + driver.session_id,
                    attachment_type=allure.attachment_type.MP4)

        # Clear videos and logs from selenoid
        if video and url_data(video_url): requests.delete(url=video_url)
        if logs and url_data(log_url): requests.delete(url=log_url)

        # Add environment info to allure-report
        with open("allure-report/environment.xml", "w+") as file:
            file.write(f"""<environment>
                <parameter>
                    <key>Browser</key>
                    <value>{browser}</value>
                </parameter>
                <parameter>
                    <key>Browser.Version</key>
                    <value>{version}</value>
                </parameter>
                <parameter>
                    <key>Executor</key>
                    <value>{executor_url}</value>
                </parameter>
            </environment>
            """)

    request.addfinalizer(finalizer)
    return driver


@pytest.fixture
def local_browser(request):
    browser = request.config.getoption("--browser")

    if browser == "chrome":
        driver = webdriver.Chrome()
    elif browser == "firefox":
        driver = webdriver.Firefox()
    else:
        raise ValueError("{} browser not supported".format(browser))

    allure.attach(
        name=driver.session_id,
        body=json.dumps(driver.desired_capabilities),
        attachment_type=allure.attachment_type.JSON)

    request.addfinalizer(driver.quit)
    return driver
