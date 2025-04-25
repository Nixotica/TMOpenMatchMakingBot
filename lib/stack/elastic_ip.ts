import { CfnOutput, Stack, StackProps } from "aws-cdk-lib";
import { CfnEIP } from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export interface ElasticIpStackProps extends StackProps {
    /** The stage of this stack (dev, prod). */
    stage: string,
}

export class ElasticIpStack extends Stack {
    constructor(scope: Construct, id: string, props: ElasticIpStackProps) {
        super(scope, id, props);

        const eip = new CfnEIP(this, `MM-Bot-ElasticIP-${props.stage}`);
        new CfnOutput(this, 'MM-Bot-ElasticIP-Output', {
            value: eip.attrPublicIp
        });
    }
}