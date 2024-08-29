import { CfnOutput } from "aws-cdk-lib";
import { AmazonLinuxCpuType, AmazonLinuxGeneration, CloudFormationInit, InitCommand, InitFile, InitService, InitSource, Instance, InstanceClass, InstanceSize, InstanceType, MachineImage, Peer, Port, SecurityGroup, ServiceManager, Vpc } from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";
import path = require("path");

export interface BotServiceConstructProps {
    /** The stage of this stack (dev, prod). */
    stage: string,
}

/**
 * A construct for hosting the bot on a t4g.nano instance. 
 */
export class BotServiceConstruct extends Construct {
    constructor(scope: Construct, id: string, props: BotServiceConstructProps) {
        super(scope, id);

        /**
         * VPC 
         */
        const vpc = new Vpc(this, 'vpc');

        /**
         * Security Group
         */
        const securityGroup = new SecurityGroup(this, 'security-group', {
            vpc,
            allowAllOutbound: true,
        });
        securityGroup.addIngressRule(Peer.ipv4(`${process.env.IP!}/32`), Port.tcp(22), 'Allow SSH access from personal device');
        securityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(443), 'Allow HTTP for Discord API');

        /**
         * EC2 Instance
         * 
         * Server hosting the discord bot. 
         */
        const source_dir = path.join(__dirname, '../mm-bot');
        const dest_dir = '/lib/mm-bot/';
        const instance = new Instance(this, `bot-server-${props.stage}`, {
            vpc,
            instanceType: InstanceType.of(InstanceClass.T4G, InstanceSize.NANO), // Est $1.67/mo
            machineImage: MachineImage.latestAmazonLinux2({
                cpuType: AmazonLinuxCpuType.ARM_64,
            }),
            init: CloudFormationInit.fromElements(
                // Create the directory for your bot if needed
                InitCommand.shellCommand(`mkdir -p ${dest_dir}`),
                
                // Install python
                InitCommand.shellCommand('yum update -y && yum install -y python3'),

                // Copy bot code into EC2 instance
                InitSource.fromAsset(dest_dir, source_dir),

                // Install dependencies from requirements.txt
                InitCommand.shellCommand(`pip3 install -r ${dest_dir}/requirements.txt`),

                // Create a systemd config file for your Discord bot service
                InitService.systemdConfigFile('discordbot', {
                    command: `/usr/bin/python3 ${dest_dir}/main.py`,
                    cwd: dest_dir,
                }),

                // Enable and start the systemd service
                InitService.enable('discordbot', {
                    serviceManager: ServiceManager.SYSTEMD,
                    enabled: true,  // Ensure it starts on boot
                }),
            ),
            securityGroup: securityGroup,
        });
        new CfnOutput(this, 'InstancePublicIP', {
            value: instance.instancePublicIp,
        });
    }
}