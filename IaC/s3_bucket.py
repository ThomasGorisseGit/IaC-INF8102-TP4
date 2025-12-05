
from troposphere import Template, s3, kms, Ref, Join, GetAtt, Output, Tags, cloudtrail, iam
from awacs.aws import Allow, Statement, Principal, Policy, Action, Condition, StringEquals
from awacs.kms import Decrypt, Encrypt, GenerateDataKey
from awacs.sts import AssumeRole

t = Template()
t.set_description("TP4 INF8102 - Secure S3 Bucket polystudens3 with KMS, Versioning, Replication, and CloudTrail")

PROJECT_NAME = "polystudentlab"
BUCKET_NAME = "polystudens3-596556162691" 
REPLICA_BUCKET_NAME = "polystudents3-back-596556162691"
MY_KMS_ARN = "arn:aws:kms:us-east-1:596556162691:key/c41c9b30-c57e-424d-aa3b-634e00109bd8"

key_policy = Policy(
    Statement=[
        Statement(
            Sid="EnableIAMUserPermissions",
            Effect=Allow,
            Principal=Principal("AWS", Join("", ["arn:aws:iam::", Ref("AWS::AccountId"), ":root"])),
            Action=[Action("kms", "*")], 
            Resource=["*"]
        ),
        Statement(
            Sid="AllowS3ServiceForEncryption",
            Effect=Allow,
            Principal=Principal("Service", "s3.amazonaws.com"),
            Action=[GenerateDataKey, Decrypt, Encrypt],
            Resource=["*"],
            Condition=Condition(
                StringEquals({
                    "kms:CallerAccount": Ref("AWS::AccountId"),
                    "kms:ViaService": Join("", ["s3.", Ref("AWS::Region"), ".amazonaws.com"])
                })
            )
        )
    ]
)

replicationRole = t.add_resource(iam.Role(
    "ReplicationRole",
    AssumeRolePolicyDocument=Policy(
        Statement=[
            Statement(
                Effect=Allow, Principal=Principal("Service", "s3.amazonaws.com"), Action=[AssumeRole]
            )
        ]
    ),
    Policies=[
        iam.Policy(
            PolicyName="ReplicationPolicy",
            PolicyDocument=Policy(
                Statement=[
                    Statement(
                        Sid="AllowSourceRead",
                        Effect=Allow,
                        Action=[
                            Action("s3", "GetObjectVersion"),
                            Action("s3", "ListBucket"),
                            Action("s3", "GetObjectVersionTagging")
                        ],
                        Resource=[
                            Join("", ["arn:aws:s3:::", BUCKET_NAME]),
                            Join("", ["arn:aws:s3:::", BUCKET_NAME, "/*"])
                        ]
                    ),
                    Statement(
                        Sid="AllowDestinationWrite",
                        Effect=Allow,
                        Action=[
                            Action("s3", "ReplicateObject"),
                            Action("s3", "ReplicateDelete"),
                            Action("s3", "ReplicateTagging")
                        ],
                        Resource=Join("", ["arn:aws:s3:::", REPLICA_BUCKET_NAME, "/*"])
                    ),
                    Statement(
                        Sid="AllowKMSUsage",
                        Effect=Allow,
                        Action=[Encrypt, Decrypt], 
                        Resource=[MY_KMS_ARN]
                    )
                ]
            )
        )
    ],
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "replication-role"])})
))


replicaBucket = t.add_resource(s3.Bucket(
    "PolystudentS3ReplicaBucket",
    BucketName=REPLICA_BUCKET_NAME,
    VersioningConfiguration=s3.VersioningConfiguration(Status="Enabled"),
    Tags=Tags({"Name": REPLICA_BUCKET_NAME})
))


s3Bucket = t.add_resource(s3.Bucket(
    "PolystudentS3Bucket",
    BucketName=BUCKET_NAME,
    
    VersioningConfiguration=s3.VersioningConfiguration(Status="Enabled"),
    
    BucketEncryption=s3.BucketEncryption(
        ServerSideEncryptionConfiguration=[
            s3.ServerSideEncryptionRule(
                ServerSideEncryptionByDefault=s3.ServerSideEncryptionByDefault(
                    KMSMasterKeyID="arn:aws:kms:us-east-1:596556162691:key/c41c9b30-c57e-424d-aa3b-634e00109bd8",
                    SSEAlgorithm="aws:kms",
                )
            )
        ]
    ),
    
    PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
        BlockPublicAcls=True, BlockPublicPolicy=True, IgnorePublicAcls=True, RestrictPublicBuckets=True
    ),
    
    ReplicationConfiguration=s3.ReplicationConfiguration(
        Role=GetAtt(replicationRole, "Arn"),
        Rules=[
            s3.ReplicationConfigurationRules( 
                Id="FullReplication",
                Status="Enabled",
                Priority=1,
                Destination=s3.ReplicationConfigurationRulesDestination(
                    Bucket=GetAtt(replicaBucket, "Arn"),
                    EncryptionConfiguration=s3.EncryptionConfiguration(
                        ReplicaKmsKeyID=MY_KMS_ARN
                    )
                ),
                SourceSelectionCriteria=s3.SourceSelectionCriteria(
                    SseKmsEncryptedObjects=s3.SseKmsEncryptedObjects(Status="Enabled")
                )
            )
        ]
    ),
    Tags=Tags({"Name": BUCKET_NAME})
))


trail = t.add_resource(cloudtrail.Trail(
    "S3ObjectAccessTrail",
    IsLogging=True,
    S3BucketName=Ref(s3Bucket), 
    IncludeGlobalServiceEvents=False,
    IsMultiRegionTrail=False, 
    
    EventSelectors=[
        cloudtrail.EventSelector(
            DataResources=[
                cloudtrail.DataResource(
                    Type="AWS::S3::Object",
                    Values=[Join("", ["arn:aws:s3:::", BUCKET_NAME, "/"])] 
                )
            ],
            IncludeManagementEvents=False, 
            ReadWriteType="All" 
        )
    ],
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "s3-cloudtrail"])})
))

t.add_output(Output("S3BucketArn", Value=Join("", ["arn:aws:s3:::", Ref(s3Bucket)]), Description="ARN of the secure S3 bucket."))
t.add_output(Output("S3ReplicaBucketArn", Value=Join("", ["arn:aws:s3:::", Ref(replicaBucket)]), Description="ARN of the replica S3 bucket."))

print(t.to_yaml())