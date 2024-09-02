import { Bucket, BucketAccessControl, BucketEncryption } from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export interface StorageConstructProps {
    /** The stage of this stack (dev, prod). */
    stage: string,

    /** The account ID this stack will be deployed to. */
    account: string,
}

/**
 * A construct for tables and buckets accessed by the bot.  
 */
export class StorageConstruct extends Construct {
    public readonly secretsBucket: Bucket;

    constructor(scope: Construct, id: string, props: StorageConstructProps) {
        super(scope, id);

        /**
         * PlayerProfiles Table
         * 
         * A table for storing player profiles consisting of:
         * - `account_id`: Player's account ID (Primary Key)
         * - `elo`: Player's elo (Number)
         * - `matches_played`: Player's cached number of matches played, negates checking results table (Number)
         */

        /**
         * MatchResults1v1v1v1 Table
         * 
         * A table for storing match results consisting of:
         * - `match_id`: Match ID (Primary Key)
         * - `queue_id`: Queue ID (Sort Key) -- the type of queue it was made for
         * - `time_played`: The time when the match was played (ISO8601 Datetime)
         * - `p1`: First place player's account ID
         * - `p2`: Second place player's account ID
         * - `p3`: Third place player's account ID
         * - `p4`: Fourth place player's account ID
         */

        /**
         * Secrets Bucket
         * 
         * A bucket to store encrypted data consisting of a file `secrets.json` of the form:
         * ```
         * { 
         *      "UBI_AUTHS": ["Basic <base64(user:pass)>", ...],
         *      "DISCORD_BOT_TOKEN": "bot_token"
         * }
         * ```
         */
        this.secretsBucket = new Bucket(this, "MMBotSecretsBucket", {
            encryption: BucketEncryption.S3_MANAGED,
            accessControl: BucketAccessControl.BUCKET_OWNER_FULL_CONTROL,
            bucketName: `tm-mm-bot-secrets-${props.stage}-${props.account}`
        })
    }
}