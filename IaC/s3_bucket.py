# Fichier : s3_bucket.py (CORRECTION FINALE pour Troposphere 4.9.5)

from troposphere import Template, s3, kms, Ref, Join, GetAtt, Output, Tags, cloudtrail, iam
from awacs.aws import Allow, Statement, Principal, Policy, Action, Condition, StringEquals
from awacs.kms import Decrypt, Encrypt, GenerateDataKey
from awacs.sts import AssumeRole

t = Template()
t.set_description("TP4 INF8102 - Secure S3 Bucket polystudens3 with KMS, Versioning, Replication, and CloudTrail")

PROJECT_NAME = "polystudentlab"
BUCKET_NAME = "polystudens3" 
REPLICA_BUCKET_NAME = "polystudents3-back" 

# --- A. Clé KMS Gérée par le Client (CMK) (Q2) ---
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

s3KMSKey = t.add_resource(kms.Key(
    "S3EncryptionKey",
    KeyPolicy=key_policy,
    Description=Join("-", [PROJECT_NAME, "s3-encryption-key"]),
    Enabled=True,
    EnableKeyRotation=True, 
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "s3-kms-key"])})
))

# ----------------------------------------------------------------------------------
# Q3.3 (1): Rôle IAM pour S3 Replication
# ----------------------------------------------------------------------------------
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
                        Resource=[GetAtt(s3KMSKey, "Arn")]
                    )
                ]
            )
        )
    ],
    Tags=Tags({"Name": Join("-", [PROJECT_NAME, "replication-role"])})
))


# ----------------------------------------------------------------------------------
# Q3.3 (1): S3 Bucket de Destination
# ----------------------------------------------------------------------------------
replicaBucket = t.add_resource(s3.Bucket(
    "PolystudentS3ReplicaBucket",
    BucketName=REPLICA_BUCKET_NAME,
    VersioningConfiguration=s3.VersioningConfiguration(Status="Enabled"),
    Tags=Tags({"Name": REPLICA_BUCKET_NAME})
))


# ----------------------------------------------------------------------------------
# Q2 & Q3.3 (1): S3 Bucket Source avec Réplication
# ----------------------------------------------------------------------------------
s3Bucket = t.add_resource(s3.Bucket(
    "PolystudentS3Bucket",
    BucketName=BUCKET_NAME,
    
    VersioningConfiguration=s3.VersioningConfiguration(Status="Enabled"),
    
    BucketEncryption=s3.BucketEncryption(
        ServerSideEncryptionConfiguration=[
            s3.ServerSideEncryptionRule(
                ServerSideEncryptionByDefault=s3.ServerSideEncryptionByDefault(
                    KMSMasterKeyID=Ref(s3KMSKey),
                    SSEAlgorithm="aws:kms",
                )
            )
        ]
    ),
    
    PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
        BlockPublicAcls=True, BlockPublicPolicy=True, IgnorePublicAcls=True, RestrictPublicBuckets=True
    ),
    
    # Q3.3 (1) Configuration de Réplication
    ReplicationConfiguration=s3.ReplicationConfiguration(
        Role=GetAtt(replicationRole, "Arn"),
        Rules=[
            s3.ReplicationConfigurationRules( 
                Id="FullReplication",
                Status="Enabled",
                Priority=1,
                Destination=s3.ReplicationConfigurationRulesDestination(
                    # CORRECTION FINALE : Retour à l'attribut 'Bucket'
                    Bucket=GetAtt(replicaBucket, "Arn"),
                    EncryptionConfiguration=s3.EncryptionConfiguration(
                        ReplicaKmsKeyID=Ref(s3KMSKey) 
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


# ----------------------------------------------------------------------------------
# Q3.3 (2): CloudTrail Trail pour le Plan de Données (Data Events)
# ----------------------------------------------------------------------------------
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

# Exporter les ARNs
t.add_output(Output("S3BucketArn", Value=Join("", ["arn:aws:s3:::", Ref(s3Bucket)]), Description="ARN of the secure S3 bucket."))
t.add_output(Output("S3ReplicaBucketArn", Value=Join("", ["arn:aws:s3:::", Ref(replicaBucket)]), Description="ARN of the replica S3 bucket."))

# Génération du template
print(t.to_yaml())