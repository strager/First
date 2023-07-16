# First!

First! is a Twitch app for the first people to join your streams.

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
   1. Visit the [Twitch application registration page](register-Twitch-app).
   2. Write any application name allowed by Twitch. Try: "First in chat"
   3. Under OAuth Redirect URLs, write: `http://localhost:5000/`
   4. Press Create.
7. Copy `first/config/config.example.toml` to `first/config/config.toml`.
8. Update `first/config/config.toml`, following the in-line
   instructions.
9. Run the First web server: `ENV/bin/tox -e flask`

## Setting up your stream

1. Create a channel point reward named "first":
   1. Visit your stream's channel point rewards settings:
      `https://dashboard.twitch.tv/u/YOURTWITCHNAME/viewer-rewards/channel-points/rewards`
   2. Create a new channel point reward with the following settings:  
      **Reward Name**: `first` (case sensitive)  
      **Require Viewer To Enter Text**: off  
      **Cost**: whatever you want (recommended: `1`)  
      **Skip Reward Request Queue**: on  
      **Cooldowns & Limits**: on  
      **Limit Redemptions Per Stream**: `1`  
      **Limit Redemptions Per User Per Stream**: `1`
   3. Press "Save".
2. Open <http://localhost:5000/>.
3. Click the "Add First! to Twitch" button at the bottom.
4. In the Twitch UI, allow the login. This should redirect you to
   your First! settings dashboard (<http://localhost:5000/manage.html>).
5. Under "Select a Reward for First", choose the reward named "first"
   that you created.
6. Press "Submit".

After viewers redeem the "first", "second", and "third" rewards, you can
see how cool they are by looking at the leaderboards:

1. Open <http://localhost:5000/>.
2. Click your stream's name in the leaderboard.

[Tox]: https://tox.wiki
[register-Twitch-app]: https://dev.twitch.tv/console/apps/create
