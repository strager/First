# First!

First! is a Twitch app for the first people to join your streams.

First! is written in Python 🐍

Key features:

* Leaderboards
* first -> second -> third progression

## Installing & running locally

1. Install Python 3.11 or newer. Ubuntu: `sudo apt install python3`
2. Install Pip. Ubuntu: `sudo apt install python3-pip`
3. Install Python venv. Ubuntu: `sudo apt install python3-venv`
4. Create a virtual Python environment: `python3 -m venv ENV`
5. Install [Tox][] in the virtual Python environment: `ENV/bin/pip install tox`.
6. Create a Twitch application:
   1. Visit the [Twitch application registration page][register-Twitch-app].
   2. Write any application name allowed by Twitch. Try: "First in chat"
   3. Under OAuth Redirect URLs, write: `http://localhost:5000/`
   4. Press Create.
7. Copy `first/config/config.example.toml` to `first/config/config.toml`.
8. Update `first/config/config.toml`, following the in-line
   instructions.
9. Run the First web server: `ENV/bin/tox -e flask`

## Setting up your stream

1. Open <http://localhost:5000/>.
2. Click the "Add First! to Twitch" button at the bottom.
3. In the Twitch UI, allow the login. This should redirect you to
   your First! settings dashboard (<http://localhost:5000/manage.html>).
4. Under "Have First! create your first channel point reward
   automatically", choose a channel point cost then press "Create
   reward".

A new channel point reward titled "first" should now be enabled for your
Twitch stream. It will automatically be changed to "second" or "third"
as appropriate.

After viewers redeem the "first", "second", or "third" rewards, you can
see how cool they are by looking at the leaderboards:

1. Open <http://localhost:5000/>.
2. Click your stream's name in the leaderboard.

[Tox]: https://tox.wiki
[register-Twitch-app]: https://dev.twitch.tv/console/apps/create
