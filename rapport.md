# Rapport d'Analyse des Vulnérabilités IaC (VPC & S3)

## I. Résumé des Vulnérabilités de Haute Sévérité

Ce rapport est basé sur l'extraction des configurations IaC (Infrastructure as Code) des templates **VPC** et **S3**, filtrées pour la sévérité **HIGH**.

### A. Vulnérabilités Spécifiques au VPC (EC2, Réseau)

| Type de Vulnérabilité            | Occurrences | Description du Risque                                                                                             |
| :------------------------------- | :---------: | :---------------------------------------------------------------------------------------------------------------- |
| **IMDS non sécurisé**            |      4      | L'accès aux métadonnées de l'instance (IMDS) n'exige pas de jeton, exposant potentiellement les identifiants IAM. |
| **Règle de Sécurité Permissive** |      1      | Un groupe de sécurité autorise un accès entrant (Ingress) illimité sur des ports d'administration.                |
| **Disque Non Chiffré**           |      4      | Les volumes de blocs ne sont pas chiffrés, mettant en danger les données au repos.                                |
| **IP Publique Automatique**      |      2      | Le sous-réseau alloue automatiquement des adresses IP publiques aux ressources.                                   |

### B. Vulnérabilités Spécifiques au S3 (Stockage)

| Type de Vulnérabilité            | Occurrences | Description du Risque                                                                                                                  |
| :------------------------------- | :---------- | :------------------------------------------------------------------------------------------------------------------------------------- |
| **Chiffrement de Bucket (Clés)** | 2           | Le chiffrement utilise des clés gérées par AWS ou est mal configuré, limitant le contrôle de la rotation (AVD-AWS-0050, AVD-AWS-0051). |
| **Validation des Logs**          | 1           | La validation des logs CloudTrail est désactivée, permettant la falsification des preuves d'activité.                                  |
| **ACL/Politique Publique**       | 4           | Le bucket n'a pas activé les mesures de blocage d'accès public (Block Public Access) au niveau des ACLs ou des politiques de bucket.   |
| **Chiffrement manquant**         | 1           | Le chiffrement est absent sur le bucket S3.                                                                                            |

---

## II. Mesures d'Atténuation et Implémentation IaC

### 1. Atténuation des Risques du VPC (EC2 & Réseau)

| Mesure                         | Implémentation IaC                                                                                     |
| :----------------------------- | :----------------------------------------------------------------------------------------------------- |
| **Forcer IMDSv2**              | Dans la ressource 'AWS::EC2::Instance', définir 'MetadataOptions.HttpTokens: required'.                |
| **Restreindre Trafic Entrant** | Limiter l'accès aux adresses IP spécifiques. Supprimer tout accès '0.0.0.0/0' sur les ports sensibles. |
| **Chiffrement des Volumes**    | Pour le bloc 'BlockDeviceMappings', définir 'Encrypted: true'.                                         |
| **Désactiver l'IP Publique**   | Pour les sous-réseaux privés ('AWS::EC2::Subnet'), définir 'MapPublicIpOnLaunch: false'.               |

### 2. Atténuation des Risques du S3 (Stockage)

| Mesure                        | Vulnérabilité Ciblée         | Implémentation IaC                                                                                                                               |
| :---------------------------- | :--------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------- |
| **Activer le Blocage Public** | ACL/Politique Publique       | Appliquer les quatre options de **Block Public Access** au niveau du bucket (blocage des ACLs et des politiques publiques).                      |
| **Chiffrement du Bucket**     | Chiffrement manquant         | Appliquer le chiffrement par défaut (SSE-S3 ou SSE-KMS) à l'aide de 'BucketEncryption'.                                                          |
| **Utiliser des Clés CMK**     | Chiffrement de Bucket (Clés) | Utiliser des clés gérées par le client (CMK) si un contrôle total sur les politiques d'accès et la rotation est requis.                          |
| **Validation des Logs**       | Validation des Logs          | Activer la validation des fichiers journaux pour CloudTrail afin de détecter et prévenir toute tentative de falsification des données de preuve. |

### 3. Mesure Globale

| Mesure                 | Description                             | Implémentation IaC                                                                                                                                                                |
| :--------------------- | :-------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Exiger le Scan IaC** | Prévention de toutes les vulnérabilités | Intégrer **Trivy config** dans le pipeline CI/CD pour que le déploiement échoue si des vulnérabilités de sévérité **HIGH** ou **CRITICAL** sont détectées (méthode "Shift Left"). |
