# Open Trackmania Matchmaking Bot

This is a WIP open source project for creating a matchmaking bot in discord. 

## Development

WARNING! Deploying a stack locally can currently cost up to $10/mo. This is primarily due to the constant uptime of the ECS task.

1. Create an AWS account. (There are multiple resources online about how to do this, and it's free). 

2. Create `.env` file in `/lib/mm-bot/` and update the required variables:
    ```
        SECRETS_BUCKET=secrets.json
        PLAYER_PROFILES_TABLE=tm-mm-bot-player-profiles-dev-<account-id>
        PLAYER_ELOS_TABLE=tm-mm-bot-player-elos-dev-<account-id>
        MATCH_RESULTS_TABLE=tm-mm-bot-match-results-dev-<account-id>
        MATCH_QUEUES_TABLE=tm-mm-bot-match-queues-dev-<account-id>
        LEADERBOARDS_TABLE=tm-mm-bot-leaderboards-dev-<account-id>
        RANKS_TABLE=tm-mm-bot-ranks-dev-<account-id>
        LEADERBOARD_RANKS_TABLE=tm-mm-bot-leaderboard-ranks-dev-<account-id>
        NEXT_BOT_MATCH_ID_TABLE=tm-mm-bot-next-bot-match-id-dev-<account-id>
        PERSISTED_MATCHES_TABLE=tm-mm-bot-persisted-matches-dev-<account-id>
        AWS_ACCESS_KEY_ID=<your-id>
        AWS_SECRET_ACCESS_KEY=<your-access-key>
        AWS_DEFAULT_REGION=<your-region>
    ```
    These will be used when you run your container locally for faster testing. 

3. Set environment variable `STAGE="dev"` on your system. This will be used to differentiate resources to deploy for prod vs development and testing. 

4. Run `cdk deploy` to deploy your stack to your AWS account. **IMPORTANT**: If you want to limit your spend, go to the AWS console and disable or terminate your ECS task and delete the flexible IP address. If you are only running the bot via your local docker container (for test or otherwise) you will not need these resources. 

5. Create a discord bot following a guide (you could follow [this one](https://www.ionos.com/digitalguide/server/know-how/creating-discord-bot/)).

6. Create `secrets.json` file anywhere, copy the snippet below, and update the required variables:
    ```
        {
            "UBI_AUTHS": ["Basic <user:pass base64>"],
            "DISCORD_BOT_TOKEN": "<token>",
            "PASTEBIN_API_DEV_KEY": "<key>"
        }
    ```
    For the username and password, use what you sign in with for Ubisoft, and enter it into [this website](https://www.base64decode.org/), making sure you switch to *encode* mode. For example, if you had username "my" and password "pass", type in "my:pass" and it would return "bXk6cGFzcw==", so you would set `"UBI_AUTHS": ["Basic bXk6cGFzcw=="]`. 

7. Go to S3 and upload `secrets.json` to the bucket `tm-mm-bot-secrets-dev-<account_id>` at the root directory. 

8. Ensure you've installed docker (easy to look up). 

9. Now you have a bot, the required infrastructure launched, and the code the bot will use in `/lib/mm-bot`. Navigate to `/lib/mm-bot` and run `docker-compose up --build` to build and run the bot locally. You should see output something like this:
    ```
        $ discord.client logging in using static token
        $ discord.gateway Shard ID None has connected to Gateway (Session ID: d77e6960cc3dbd8d6201ce02f47c0d3d).
    ```

10. Go to the server with the bot added to it, and try running some commands. Now you can either use it or continue to develop this bot. Enjoy!

11. To stop running the bot, you should run `docker-compose stop` from the same directory (in a separate terminal instance if your logs are being output to the first instance), which will run through the necessary tear-down steps to remove queues from the discord server channels, etc. 

## Testing

For unit/integ tests, you'll want to use pytest. Simply install python3.11 locally, navigate to `/lib/mm-bot` and run `python3.11 -m pip install -r requirements.txt` then `python3.11 -m pytest`. 

## Gotchas

There currently isn't any CI/CD so deploying to prod is done from command line by running `export STAGE=prod` and then deploying. However, this *sometimes* makes the nadeo event api out of date, and it will cause deployment to fail. In that case, run `git ls-remote https://github.com/Nixotica/NadeoEventAPIWrapper.git release`, copy the hash, and paste it in `requirements.txt` instead of "release" in the final line. 

## Commands

### Create Queue

Creating a new queue means creating a set of maps which are tied to an in-game campaign, for which a single random map in that campaign will be selected during a match. This queue will occupy a dedicated discord text channel, and can ping players who opt into a role dedicated to that queue, and can contribute to a number of assigned leaderboards upon players completed matches in that queue.

#### Usage:

`/create_queue <queue_id> <campaign_club_id> <campaign_id> <match_club_id> <channel_id> <type>`

#### Parameters:

* `queue_id` - The identifier for the queue, also the name which will be displayed for the queue. 

* `campaign_club_id` - The ID of the club which contains the campaign to use for the maps in the queue. Can be found on TMIO: `https://trackmania.io/#/clubs/<campaign_club_id>`

* `campaign_id` - The ID of the campaign to use for the maps in the queue. Can be found on TMIO: `https://trackmania.io/#/campaigns/<campaign_club_id>/<campaign_id>`

* `match_club_id` - The ID of the club which hosts the Nadeo events or "matches" generated by the queue. 

* `channel_id` - The ID of the discord channel to display the queue, allowing players to join and receive pings for the queue. 

* `type` - The type of queue this is for. Currently supports `1v1v1v1` and `2v2` as valid types. 

### Add Queue to Leaderboard

TODO

### List Queues

TODO 

### Link Ping Role to Queue

TODO

### Set Primary Leaderboard for Queue

TODO

### Create Leaderboard

TODO

### List Leaderboards

TODO

### Refresh Leaderboards

TODO

### Set Main Leaderboard

TODO

### Create Rank

TODO

### Link Rank Role

TODO

### Refresh Player Rank

TODO

### Set Bot Messages Channel

TODO

### Link Pings Role

TODO

### Cancel Match

TODO

### Ping

Pings the bot messages channel with `Pong!`

#### Usage

`/ping`

## Contact

The current owner and sole contributor to this package is @Nixotica, available on most platforms via that same alias. 