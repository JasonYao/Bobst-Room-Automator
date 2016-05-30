# Application imports
import io
import requests
import csv
import logging
from collections import deque
import datetime

# Settings imports
import settings

# Web-driver imports
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec

# Google API requirements & imports
import httplib2
import os
from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools
import argparse


# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Bobst Room Automator'

month_dict = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


try:
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None


def setup_logging(date):
    log_format = "%(asctime)s: %(levelname)s: %(message)s"
    logging.basicConfig(
        format=log_format,
        filename='log/' + date.isoformat() + '.log',
        level=logging.INFO)

    # Setup the console handler with a StringIO object
    log_capture_string = io.StringIO()
    ch = logging.StreamHandler(log_capture_string)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(log_format)
    ch.setFormatter(formatter)

    # Add the console handler to the logger
    root = logging.getLogger()
    root.addHandler(ch)

    logging.info("Start of Bobst Room Automator program")
    return log_capture_string


class User:
    username = ""
    password = ""
    status = "NOT_STARTED"


def create_users():
    """
    Creates each user
    """
    logging.info("Creating users")
    users = set()

    with open(settings.user_login_file, newline='') as csvfile:
        csv_reader = csv.reader(csvfile, delimiter=',', quotechar='|')
        for row in csv_reader:
            new_user = User()
            new_user.username = row[0]
            new_user.password = row[1]
            users.add(new_user)
            logging.info("User %s created", row[0])
    logging.info("%d users created", len(users))
    return users


def get_credentials():
    """
    Gets valid user credentials from storage.
    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.
    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'bobst-room-automator.json')
    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else:  # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials


def to_string_month(month_int):
    return month_dict[month_int]


def book_room(user, start_date, start_time, browser):
    logging.info("START of room booking")
    browser.get("http://rooms.library.nyu.edu/")

    # Logs into NYU network
    logging.info("Logging user %s in", user.username)
    browser.find_element_by_id("nyu_shibboleth-login").click()
    browser.find_element_by_id("netid").send_keys(user.username)
    browser.find_element_by_id("password").send_keys(user.password)
    browser.find_element_by_name("_eventId_proceed").click()

    # Tests for invalid login
    logging.info("TESTING: Invalid login")
    try:
        browser.find_element_by_id("loginError")
        raise InvalidUserCredentialError("User: " + user.username + "'s login information is incorrect", start_time)
    except NoSuchElementException:
        logging.info("User %s's login information is valid", user.username)

    # Selects start date from datepicker
    logging.info("Selecting start date from date-picker")
    WebDriverWait(browser, 10).until(ec.presence_of_element_located((By.ID, "room_reservation_which_date")))
    browser.find_element_by_id("room_reservation_which_date").click()

    # Moves date-picker year until correct is found
    logging.info("Selecting year from date-picker")
    while browser.find_element_by_class_name("ui-datepicker-year").text != str(start_date.year):
        browser.find_element_by_class_name("ui-icon-circle-triangle-e").click()
    logging.info("Selected year: %s", browser.find_element_by_class_name("ui-datepicker-year").text)

    # Moves date-picker month until correct is found
    logging.info("Selecting month from date-picker")
    while browser.find_element_by_class_name("ui-datepicker-month").text != to_string_month(start_date.month):
        browser.find_element_by_class_name("ui-icon-circle-triangle-e").click()
    logging.info("Selected month: %s", browser.find_element_by_class_name("ui-datepicker-month").text)

    # Selects correct date
    logging.info("Selecting correct date from datepicker")
    browser.find_element_by_link_text(str(start_date.day)).click()
    logging.info("Date selected was: %d", start_date.day)

    # Time selection
    original_start_time = start_time
    is_am = True
    if start_time == 12:
        is_am = False
    elif start_time > 12:
        is_am = False
        start_time -= 12

    # Starts selecting the time of the booking
    logging.info("Inputting required information")
    WebDriverWait(browser, 10).until(ec.presence_of_element_located((By.ID, "reservation_hour")))
    Select(browser.find_element_by_id("reservation_hour")).select_by_value(str(start_time))
    Select(browser.find_element_by_id("reservation_minute")).select_by_value("0")

    if is_am:
        Select(browser.find_element_by_id("reservation_ampm")).select_by_value("am")
    else:
        Select(browser.find_element_by_id("reservation_ampm")).select_by_value("pm")
    Select(browser.find_element_by_id("reservation_how_long")).select_by_value("120")
    logging.info("Required information has been input")

    # Submits date + time, and opens up room selection window
    logging.info("Opening room selection window")
    browser.find_element_by_id("generate_grid").click()

    # Tests for already-booked status
    try:
        WebDriverWait(browser, 30).until(
            ec.presence_of_element_located((By.XPATH, "//div[@class='alert alert-danger']")))
        raise InvalidUserCredentialError("User: " + user.username + " has already booked a room for today",
                                         original_start_time)
    except TimeoutException:
        logging.info("User %s has not booked a room for today yet", user.username)

    # Finds the room
    logging.info("Start of room booking")
    room_text = "Bobst " + settings.floor_number + "-" + str(settings.room_number)

    # Tests for room already booked error
    try:
        logging.info("TESTING: If room is already booked")
        WebDriverWait(browser, 30).until(ec.presence_of_element_located((By.ID, "availability_grid_table")))
        logging.info("Room selection has been opened and detected")
        browser.find_element_by_xpath("//div[contains(text(), '" + room_text + "')]").click()
        logging.info("Room was found")
    except NoSuchElementException:
        raise InvalidTimeSlotError("Time-slot is already booked, re-adding user " + user.username +
                                   " to the active user pool", user)
    logging.info("Room has been selected")

    # Inputs required user information
    logging.info("Sending required user info")
    browser.find_element_by_id("reservation_cc").send_keys(user.username + "+NYU@nyu.edu")
    browser.find_element_by_id("reservation_title").send_keys(settings.description)
    logging.info("Required user info sent")

    # Submits
    browser.find_element_by_xpath("//button[contains(text(),'Reserve selected timeslot')]").click()
    logging.info("Room request has been sent")

    # Testing for valid submission
    try:
        WebDriverWait(browser, 30).until(
            ec.presence_of_element_located((By.XPATH, "//div[@class='alert alert-success']")))
        logging.info("Room has successfully been booked")
    except NoSuchElementException:
        logging.warning("Unable to detect successful room submission")

    summary = "END of room booking for user " + user.username + " with time " + str(start_time) + " "
    if is_am:
        summary += "AM"
    else:
        summary += "PM"
    logging.info(summary)
    return


def update_calendar(room_number, start, end):
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    event = {
        'summary': 'Bobst Study Room',
        'location': 'Room ' + room_number + ', Bobst Library, Washington Square South, New York, NY, United States',
        'description': 'Available study room for Phi Kappa Sigma members on campus',
        'start': {
            'dateTime': start,
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': end,
            'timeZone': 'America/New_York',
        },
        'attendees': settings.attendees,
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }
    event = service.events().insert(
        calendarId=settings.schedule_id, body=event).execute()

    logging.info("Event created for " + start + ": " + event.get('htmlLink'))
    return


def email(subject, log):
    # Pull the contents back into a string and close the stream
    logging.info("All users booked, emailing summary now")
    log_contents = log.getvalue()

    return requests.post(
        "https://api.mailgun.net/v3/skullhouse.nyc/messages",
        auth=("api", settings.api_key),
        data={"from": settings.from_email,
              "to": settings.to_email,
              "subject": subject,
              "text": log_contents})


def main():
    """
    Runs through and books a room. Creates a Google Calendar API service object, and adds that event to the list.
    """
    time_queue = deque(settings.time_preference)
    start_date = datetime.date.today() + datetime.timedelta(days=settings.time_delta)
    end_date = start_date
    log_capture_string = setup_logging(start_date)
    active_users = create_users()

    while len(active_users) != 0:
        current_user = active_users.pop()
        start_time = time_queue.popleft()
        end_time = start_time + 2

        # Check if end time is the day after start date
        if end_time == 24:
            end_time = 0
            end_date += datetime.timedelta(days=1)

        start_datetime = start_date.isoformat() + "T" + str(start_time) + ":00:00"
        end_datetime = end_date.isoformat() + "T" + str(end_time) + ":00:00"

        browser = webdriver.Firefox()
        # noinspection PyBroadException
        try:
            book_room(current_user, start_date, start_time, browser)
            update_calendar(settings.floor_number + "-" + str(settings.room_number), start_datetime, end_datetime)
        except InvalidUserCredentialError as e:
            warning_message, unused_start_time = e.args
            logging.warning(warning_message)
            logging.info("Re-adding unused time %d", unused_start_time)
            time_queue.appendleft(unused_start_time)
        except InvalidTimeSlotError as e:
            warning_message, unused_user = e.args
            logging.warning(warning_message)
            logging.info("Re-adding unused user %s", unused_user.username)
            active_users.add(unused_user)
        except Exception:
            logging.warning("An unknown error occurred")
        finally:
            logging.info("Cleaning up browser")
            browser.implicitly_wait(10)
            browser.quit()

    email("Bobst study room booked: " + start_date.isoformat(), log_capture_string)
    log_capture_string.close()
    return


# Exceptions
class InvalidUserCredentialError(Exception):
    pass


class InvalidTimeSlotError(Exception):
    pass


if __name__ == '__main__':
    main()
