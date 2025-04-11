# Open Trackmania Matchmaking Bot

This is a WIP open source project for creating a matchmaking bot in discord. 

## Production 

Due to the limitations with association an elastic IP to EC2 instances on ECS, we are just doing it manually. This seems to keep the IP even when making updates to the ECS task (which is good because this happens every time we push a new code change). The steps to associate a new IP, in the case that ever happens (or you are developing with the bot-service stack enabled) do the following:

1. Go to AWS Console, VPC section

2. Click on "Elastic IPs" and select the IP address created by the CDK.

3. Click "Associate Elastic IP address" and associate it to the EC2 instance defined by CDK (dev/prod depending on the circumstances). 

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

4. If this is the first time building the stack, run `cdk bootstrap` to bootstrap the resources being deployed

5. Run `cdk deploy` to deploy your stack to your AWS account. **IMPORTANT**: If you want to limit your spend, go to the AWS console and disable or terminate your ECS task and delete the flexible IP address. If you are only running the bot via your local docker container (for test or otherwise) you will not need these resources. 

6. Create a discord bot following a guide (you could follow [this one](https://www.ionos.com/digitalguide/server/know-how/creating-discord-bot/)).

7. Create `secrets.json` file anywhere, copy the snippet below, and update the required variables:
    ```
        {
            "UBI_AUTHS": ["Basic <user:pass base64>"],
            "DISCORD_BOT_TOKEN": "<token>",
            "PASTES_IO_LOGIN": "<username>",
            "PASTES_IO_PASSWORD": "<password>"
        }
    ```
    For the username and password, use what you sign in with for Ubisoft, and enter it into [this website](https://www.base64decode.org/), making sure you switch to *encode* mode. For example, if you had username "my" and password "pass", type in "my:pass" and it would return "bXk6cGFzcw==", so you would set `"UBI_AUTHS": ["Basic bXk6cGFzcw=="]`. 

8. Go to S3 and upload `secrets.json` to the bucket `tm-mm-bot-secrets-dev-<account_id>` at the root directory. 

9. Ensure you've installed docker (easy to look up). 

10. Now you have a bot, the required infrastructure launched, and the code the bot will use in `/lib/mm-bot`. Navigate to `/lib/mm-bot` and run `docker-compose up --build` to build and run the bot locally. You should see output something like this:
    ```
        $ discord.client logging in using static token
        $ discord.gateway Shard ID None has connected to Gateway (Session ID: d77e6960cc3dbd8d6201ce02f47c0d3d).
    ```

11. Go to the server with the bot added to it, and try running some commands. Now you can either use it or continue to develop this bot. Enjoy!

12. To stop running the bot, you should run `docker-compose stop` from the same directory (in a separate terminal instance if your logs are being output to the first instance), which will run through the necessary tear-down steps to remove queues from the discord server channels, etc. 

### Windows development differences

There's a minor change to the `docker-compose.yaml` file that needs to be made if you're running on windows. Instead of `0.0.0.0` for the localhost definition, use `127.0.0.1` for both. 

## Testing

For unit/integ tests, you'll want to use pytest. Simply install python3.11 locally, navigate to `/lib/mm-bot` and run `python3.11 -m pip install -r requirements.txt` then `python3.11 -m pytest`. 

## Committing and Pull Requests

If you want to make commits and pull requests to master, there are a few different requirements, since a GitHub action will deploy changes from master into the production environment in AWS, immediately taking effect on the bot (if tests pass). So you will need:

1. Install pre-commit

2. Run `pre-commit install --config lib/mm-bot/.pre-commit-config.yaml`

3. Run `pre-commit run --config lib/mm-bot/.pre-commit-config.yaml --all-files` and address all issues.

4. Make your pull request, which will validate the same checks. 

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