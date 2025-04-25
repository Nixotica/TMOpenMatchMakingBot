#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { StorageStack } from '../lib/stack/storage';
import { BotServiceStack } from '../lib/stack/bot_service';
import { ElasticIpStack } from '../lib/stack/elastic_ip';

const app = new cdk.App();
const env = {
  account: "115984396435",
  region: 'us-west-2',
}

// For local testing, make sure you've run `export STAGE=dev`
if (process.env.STAGE == 'dev') {
  const storage = new StorageStack(app, 'TmOpenMatchMakingBotStack-Storage-dev', {
    env: env,
    stage: 'dev',
    account: env.account,
  })
  // NOTE this costs significant money, keep it commented out when not testing changes to the deployed service
  // new BotServiceStack(app, 'TmOpenMatchMakingBotStack-BotService-dev', {
  //   env: env,
  //   stage: 'dev',
  //   secretsBucket: storage.secretsBucket,
  //   playerProfilesTable: storage.playerProfilesTable,
  //   playerElosTable: storage.playerElosTable,
  //   matchResultsTable: storage.matchResultsTable,
  //   matchQueuesTable: storage.matchQueuesTable,
  //   leaderboardsTable: storage.leaderboardsTable,
  //   ranksTable: storage.ranksTable,
  //   leaderboardRanksTable: storage.leaderboardRanksTable,
  //   nextBotMatchIdTable: storage.nextBotMatchIdTable,
  //   persistedMatchesTable: storage.persistedMatchesTable,
  //   terminationProtection: false,
  // })
} else if (process.env.STAGE == 'prod') {
  const storage = new StorageStack(app, 'TmOpenMatchMakingBotStack-Storage-prod', {
    env: env,
    stage: 'prod',
    account: env.account,
    terminationProtection: true,
  }) 
  new BotServiceStack(app, 'TmOpenMatchMakingBotStack-BotService-prod', {
    env: env,
    stage: 'prod',
    secretsBucket: storage.secretsBucket,
    playerProfilesTable: storage.playerProfilesTable,
    playerElosTable: storage.playerElosTable,
    matchResultsTable: storage.matchResultsTable,
    matchQueuesTable: storage.matchQueuesTable,
    leaderboardsTable: storage.leaderboardsTable,
    ranksTable: storage.ranksTable,
    leaderboardRanksTable: storage.leaderboardRanksTable,
    nextBotMatchIdTable: storage.nextBotMatchIdTable,
    persistedMatchesTable: storage.persistedMatchesTable,
    terminationProtection: true,
  })
  new ElasticIpStack(app, 'TmOpenMatchMakingBotStack-ElasticIp-prod', {
    env: env,
    stage: 'prod',
    terminationProtection: true,
  })
} else {
  throw new Error(`Unsupported stage, must be one of "dev" or "prod", received ${process.env.STAGE}`)
}