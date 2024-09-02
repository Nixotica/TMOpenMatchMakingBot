import { Stack, StackProps } from "aws-cdk-lib";
import { Construct } from "constructs";
import { StorageConstruct } from "./storage";
import { BotServiceConstruct } from "./bot_service";

export interface TmOpenMatchMakingBotStackProps extends StackProps {
    /** The stage of this stack (dev, beta, prod, etc) */
    stage: string,
}

export class TmOpenMatchMakingBotStack extends Stack {
    constructor(scope: Construct, id: string, props: TmOpenMatchMakingBotStackProps) {
        super(scope, id, props);

        const storage = new StorageConstruct(this, 'Storage', {
            ...props,
            account: this.account,
        });
        new BotServiceConstruct(this, 'BotServiceStack', {
            ...props,
            secretsBucket: storage.secretsBucket,
        });
    }
}