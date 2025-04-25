import * as cdk from 'aws-cdk-lib';
import { Stack, StackProps } from 'aws-cdk-lib';
import { Role, AccountPrincipal, ManagedPolicy } from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class ReadOnlyAccessStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Replace with the external user's AWS Account ID
    const matrixAccountId = '777648093137';

    // Optional: external ID for extra security
    const externalId = 'readonly-access-guest';

    const role = new Role(this, 'ReadOnlyCrossAccountRole', {
      roleName: 'ReadOnlyGuestAccess',
      assumedBy: new AccountPrincipal(matrixAccountId),
      externalIds: [externalId],
      description: 'Allows cross-account read-only access for external users',
      managedPolicies: [
        ManagedPolicy.fromAwsManagedPolicyName('ReadOnlyAccess'),
      ],
    });

    new cdk.CfnOutput(this, 'OneClickLoginUrl', {
        value: `https://signin.aws.amazon.com/switchrole?account=${this.account}&roleName=${role.roleName}&displayName=ReadOnly`,
        description: 'One-click login URL for the external user to assume the read-only role',
      });
  }
}
