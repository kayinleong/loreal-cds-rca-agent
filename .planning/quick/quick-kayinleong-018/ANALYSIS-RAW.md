# FINDINGS — Real-incident analysis of ticketasg routing

Total incidents analysed: **64**
Distinct current groups: **4**

## 1. Current assignment-group distribution

| # | Current Group | Incidents | % |
|---|---|---:|---:|
| 1 | `APAC - SGP - SPACE CDS SAPMENA L3 Support` | 22 | 34.4% |
| 2 | `APAC - ZN - SPACE B2C Hypercare` | 19 | 29.7% |
| 3 | `APAC - SGP - SPACE CDS SAPMENA L2 Support` | 16 | 25.0% |
| 4 | `APAC - CHN - SPACE Loyalty L3 Support` | 7 | 10.9% |

- Canonical groups (10 supported) **with** incidents in this sample: **2/10**
- Canonical groups with **no** incidents in this sample:
  - `APAC - THN - Retail IT`
  - `APAC - ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2`
  - `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2`
  - `APAC - ZN - O+O.CRM - L2`
  - `APAC - ZN - O+O.NGLORA - L2`
  - `APAC - ZN - O+O.OPERATIONS - L2`
  - `APAC - ZN - iBeauty 2.0 - Retail - L2`
  - `TECH FNDN - WW - HIP INCIDENT L2`
- **Out-of-scope** groups present in this sample (tickets currently sit outside the 10 canonical groups):
  - `APAC - CHN - SPACE Loyalty L3 Support` (7 incidents)
  - `APAC - SGP - SPACE CDS SAPMENA L3 Support` (22 incidents)

## 2. Per-incident routing trace

Each row scores the incident text against the existing `assignment_rules.json` keywords.
`Match?` = `✓` when the current SNOW group equals the keyword-predicted group.

| # | Incident | Short Description | Current Group | Predicted (by current rules) | Hits | Conf | Match? |
|---|---|---|---|---|---|---:|:---:|
| 1 | `INC10413436` | SG, MY, HK, JP \| All Brands \| GetCustomerById, GetPurchaseV2 , GetCalculatedAttributes API | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP | 0.21 | ✗ |
| 2 | `INC10419095` | MY , SG \| YSL, kiehls \|  POST Customer/GetCustomerById [v] API failure | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP, SAPMENA, Singapore | 0.31 | ✓ |
| 3 | `INC10487330` | ANZ \| Campaign data missing from Campaigns table. Broken campaign target/response foreign  | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.29 | ✓ |
| 4 | `INC10387135` | P2 Alert received due to FindConsumerProfile failure with 504 error | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP, SAPMENA | 0.36 | ✓ |
| 5 | `INC10328738` | MY/KIE- After migration both ID found under prospect and couldn't found in MARs system or  | SGP - SPACE CDS SAPMENA L2 Support | WW - HIP INCIDENT L2 | HIP, database, server | 0.23 | ✗ |
| 6 | `INC10482324` | [RETAIL] : iBeauty 2.0 - APAC: Unable to search customer details | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP | 0.25 | ✓ |
| 7 | `INC10453163` | ID SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA | 0.43 | ✓ |
| 8 | `INC10462256` | TH SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA | 0.5 | ✓ |
| 9 | `INC10462212` | MY SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS | 0.25 | ✓ |
| 10 | `INC10450026` | CDS Infrastructure - CloudSQL not syncing data to Replica | SGP - SPACE CDS SAPMENA L2 Support | WW - HIP INCIDENT L2 | cloud, database, infrastructure | 0.6 | ✗ |
| 11 | `INC10367950` | MTY\| LAN \|Customer Purchase on member days 29/3/26 RM4510 x 3points= 13530 points but poin | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O.CRM - L2 | CRM, account, lucid | 0.25 | ✗ |
| 12 | `INC10312845` | SG/KIE-This member account can't find in MARS and also his personal details on the IBeauty | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O.CRM - L2 | account, loyalty, lucid | 0.27 | ✗ |
| 13 | `INC10293500` | [MARS-ANZ] Sales representative does not exist | SGP - SPACE CDS SAPMENA L2 Support | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Capgemini, GDC, MARS, OMNISALES, omni | 0.36 | ✗ |
| 14 | `INC10457408` | ANZ \| Patching locationid and salesrepid in AESOP | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS | 0.33 | ✗ |
| 15 | `INC10431241` | TH Generic Tourist Others Profile closed | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Capgemini, MARS | 0.5 | ✗ |
| 16 | `INC10429906` | Failed to insert batch into stg_sap_product_hierarchy: numeric field overflow | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.5 | ✗ |
| 17 | `INC10304697` | CRM Lite brands not migrated with accurate last update date from SFMC resulting in incorre | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, Singapore | 0.3 | ✗ |
| 18 | `INC10320937` | SG/YSL-The points has not been reflected in membership account. | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O.CRM - L2 | CRM, account, loyalty, lucid | 0.29 | ✗ |
| 19 | `INC10483228` | ANZ \| Invalid SFMC Prospects Ingested | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.5 | ✓ |
| 20 | `INC10231059` | TH ALL-R12M purchase amount is always not showing on Ibeauty. | SGP - SPACE CDS SAPMENA L2 Support | ZN - O+O.OPERATIONS - L2 | API, batch, ops | 0.27 | ✗ |
| 21 | `INC10430912` | MY/LAN-Rebind the order to the correct LUCID. | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | account, loyalty, lucid | 0.25 | ✗ |
| 22 | `INC10420625` | AUS \| KER \| customer has no records on account 288560 | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | account, loyalty, lucid | 0.23 | ✗ |
| 23 | `INC10381009` | MY/KIE-To seek clarify on the point adjustment appear in the point history page. | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | SAP | 0.17 | ✗ |
| 24 | `INC10466783` | [LCM] Request for Deletion of Loyalty Account Data SFDC: 01326210 | CHN - SPACE Loyalty L3 Support | ZN - O+O.CRM - L2 | account, loyalty, lucid | 0.25 | ✗ |
| 25 | `INC10471722` | MY/KIE-Please help activate the customer's account. | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O.CRM - L2 | account, consumer profile, loyalty, lucid | 0.44 | ✗ |
| 26 | `INC10142664` | SG \| KIE \| UNABLE TO MERGE DUPLICATE ACCOUNT | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | CRM, account, consumer profile, lucid | 0.44 | ✗ |
| 27 | `INC10449165` | TH Lancome Customer profile closed and not earn points | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O.CRM - L2 | CRM, loyalty, lucid | 0.3 | ✗ |
| 28 | `INC10394746` | TH \| LAN \| Duplicated Mar ID | SGP - SPACE CDS SAPMENA L3 Support | WW - HIP INCIDENT L2 | HIP, database, server | 0.21 | ✗ |
| 29 | `INC10199563` | [E2E TESTING] TH YSL- Account registered via EBTQ shows incorrect creation counter | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | CRM, account, loyalty, lucid, marketing, registration | 0.2 | ✗ |
| 30 | `INC10475182` | SFMC Prospect Ingestion incorrectly updating sourceLastUpdatedDatetime to current UTC time | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.25 | ✓ |
| 31 | `INC10384818` | Please check customer with phone number in Kiehl's | SGP - SPACE CDS SAPMENA L2 Support | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Capgemini, MARS | 0.22 | ✗ |
| 32 | `INC10377206` | VN SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.25 | ✓ |
| 33 | `INC10421600` | CDS Consumer Registration - Default Optins to include SMS for SG, MY, TH | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.25 | ✗ |
| 34 | `INC10080190` | MY \| GAB \| Profile different between iBeauty and MARS | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O.CRM - L2 | account, loyalty, lucid | 0.21 | ✗ |
| 35 | `INC10442394` | E2E Monitoring \| SAPMENA PRD \| All Brands \| SFCC -> CDS Missing Order APR | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA | 0.38 | ✗ |
| 36 | `INC10422037` | MY-LAN:customer account could not be found in SPACE | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.2 | ✗ |
| 37 | `INC10466356` | API Issue \|\| Cloudfare error from Arvato endpoint for multiple exchanges across Production | CHN - SPACE Loyalty L3 Support | WW - HIP INCIDENT L2 | HIP, SSL, auth, cloud, server | 0.29 | ✗ |
| 38 | `INC10209070` | ID \| KIE \| Customer cannot be found in iBeauty despite being registered in MARS | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP | 0.38 | ✗ |
| 39 | `INC10228919` | ID \| Customer service mentioned that they could not find the customer's information, but i | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.2 | ✗ |
| 40 | `INC10453953` | MY/KIE-Historical points have not been credited. | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | loyalty, lucid | 0.29 | ✗ |
| 41 | `INC10343465` | MY/KIE-Order and points have not been credited. | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | account, lucid | 0.29 | ✗ |
| 42 | `INC10315765` | UT-O: [MARS-ANZ] CRM Customer in rejections | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.25 | ✗ |
| 43 | `INC10297852` | MY/KIE-The order and the corresponding points have not been recorded. | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | CRM, account, loyalty, lucid | 0.25 | ✗ |
| 44 | `INC10166077` | \|TH\| \|YSL\| Missing Order Issue: Discrepancy between MARS and SPACE LOYALTY regarding custo | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | CRM, loyalty, lucid | 0.2 | ✗ |
| 45 | `INC10462250` | SG SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA | 0.5 | ✓ |
| 46 | `INC10395005` | SG\|YSL\|Birthday Call List | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.33 | ✗ |
| 47 | `INC10378086` | Master Data Cleanup for Kiehls / Lancome | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.33 | ✗ |
| 48 | `INC10439424` | FirstTransactionXXX Tags have wrong value | CHN - SPACE Loyalty L3 Support | ZN - O+O.CRM - L2 | loyalty, lucid | 0.4 | ✗ |
| 49 | `INC10415946` | MY \| KIE \| Members' Points not Reflection in iBeauty (2nd Raise) | ZN - SPACE B2C Hypercare | WW - HIP INCIDENT L2 | HIP, SSO, database, platform | 0.2 | ✗ |
| 50 | `INC10284821` | TH All Brands : Incorrect Lucid and Mars ID in C360 | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, pipeline | 0.17 | ✗ |
| 51 | `INC10429974` | Receipt Query - Wrong Brand Name for Shu ION | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Capgemini, MARS | 0.4 | ✗ |
| 52 | `INC10301307` | E2E monitoring \| JP PRD  \| CDS vs LOY Same MarsId with different Lucid-0301-0314 | CHN - SPACE Loyalty L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, ERP, SAP | 0.23 | ✗ |
| 53 | `INC10367251` | RITM7405487 \| E2E Monitoring \| TH, ID PRD\| All Brands \| LOY -> Recon Dashboard (Data Lens) | CHN - SPACE Loyalty L3 Support | SGP - SPACE CDS SAPMENA L2 Support | SAP | 0.33 | ✗ |
| 54 | `INC10190808` | TH \| LAN \| Creation counter missing on C360 | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | CRM, account, lucid | 0.19 | ✗ |
| 55 | `INC10324255` | [MARS-VN,ID] Customer in rejections | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP | 0.29 | ✗ |
| 56 | `INC10081673` | TH Tourist Others customer type to fix | SGP - SPACE CDS SAPMENA L3 Support | ZN - SPACE B2C Hypercare | B2C, critical, hypercare, launch | 0.27 | ✗ |
| 57 | `INC10310154` | TH YSL Other Tourist code keeps closed | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Capgemini, MARS | 0.33 | ✗ |
| 58 | `INC10300640` | TH KIE Local Generic code issue | SGP - SPACE CDS SAPMENA L3 Support | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Capgemini, MARS | 0.25 | ✗ |
| 59 | `INC10396182` | CAPLINERR003-Linux Host-HKAPACLOYAPD2A FS /mnt/aupd usage above 90 in last 10 mi | CHN - SPACE Loyalty L3 Support | ZN - iBeauty 2.0 - Retail - L2 | BA | 0.25 | ✗ |
| 60 | `INC10114698` | Indonesia: None of the orders coming into LOY eventhough status is delivered | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA | 0.18 | ✗ |
| 61 | `INC10403825` | SHU JP Returned Order – Rule-500 AR Subscription Points Not Reversed | CHN - SPACE Loyalty L3 Support | SGP - SPACE CDS SAPMENA L2 Support | SAP | 0.25 | ✗ |
| 62 | `INC10204372` | [MARS-MY], [MARS-TH] [MARS-SG] CRM Customer in rejections | ZN - SPACE B2C Hypercare | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | Capgemini, MARS | 0.33 | ✗ |
| 63 | `INC10190032` | E2E Monitoring \| SG Prod \| All Brands \| Missing Orders 0101-0131 MARS channel for SPACE (L | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | CDS, SAP, SAPMENA, SPACE CDS, Singapore | 0.42 | ✗ |
| 64 | `INC10282648` | RITM7326831 \| MY\|YSL\|Customer Loyalty Redemption Trends & Product Performance | ZN - SPACE B2C Hypercare | ZN - O+O.NGLORA - L2 | points, redemption, tier | 0.27 | ✗ |

**Match rate (current group = predicted group): 11/64 = 17.2%**

Of incidents currently assigned to a canonical group (35), current rules correctly predict **11** = 31.4%.

## 3. Per-group real-text signals vs current keywords

For each group (with at least 1 incident in this sample), the table shows:
- **Top tokens** observed in real incident text (after stopword removal)
- **Current keywords** from `assignment_rules.json` and whether each one actually matched

### `APAC - ZN - SPACE B2C Hypercare` — 19 incidents

**Top 20 real tokens** (count):

| Token | Count |
|---|---:|
| `comment` | 262 |
| `additional` | 244 |
| `lucid` | 234 |
| `accenture` | 229 |
| `mars` | 222 |
| `work` | 219 |
| `cds` | 218 |
| `notes` | 216 |
| `private` | 216 |
| `customer` | 165 |
| `sapient` | 148 |
| `orders` | 125 |
| `check` | 120 |
| `loy` | 110 |
| `need` | 80 |
| `code` | 79 |
| `daniel` | 79 |
| `ltimindtree` | 76 |
| `yeo` | 76 |
| `limited` | 75 |

**Current `assignment_rules.json` keywords for this group:**

`hypercare`, `go live`, `go-live`, `launch`, `cutover`, `P1`, `escalation`, `new market`, `B2C`, `regression`, `critical`

### `APAC - SGP - SPACE CDS SAPMENA L2 Support` — 16 incidents

**Top 20 real tokens** (count):

| Token | Count |
|---|---:|
| `accenture` | 189 |
| `comment` | 148 |
| `additional` | 133 |
| `work` | 130 |
| `notes` | 129 |
| `private` | 125 |
| `cds` | 123 |
| `mars` | 111 |
| `hanizam` | 73 |
| `sofia` | 73 |
| `customer` | 59 |
| `wang` | 59 |
| `sherlyn` | 56 |
| `check` | 52 |
| `consumer` | 50 |
| `code` | 41 |
| `help` | 41 |
| `sales` | 41 |
| `found` | 40 |
| `update` | 38 |

**Current `assignment_rules.json` keywords for this group:**

`SAP`, `SAPMENA`, `SGP`, `Singapore`, `pipeline`, `CDS`, `SPACE CDS`, `SAP order`, `product sync`, `ERP`

## 4. Per-keyword diagnostic (across ALL incidents)

How often each keyword in `assignment_rules.json` actually matches text in the sample,
and how often that match lined up with the keyword's group being the **current** group.

| Group | Keyword | Total hits | Hits in *its own* group | Drift¹ |
|---|---|---:|---:|---:|
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `SAP` | 50 | 12 | 0.76 |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `SAPMENA` | 10 | 5 | 0.5 |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `SGP` | 0 | 0 |  |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `Singapore` | 3 | 1 | 0.67 |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `pipeline` | 1 | 0 | 1.0 |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `CDS` | 57 | 16 | 0.72 |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `SPACE CDS` | 1 | 0 | 1.0 |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `SAP order` | 0 | 0 |  |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `product sync` | 0 | 0 |  |
| `APAC - SGP - SPACE CDS SAPMENA L2 Suppor…` | `ERP` | 10 | 4 | 0.6 |
| `APAC - THN - Retail IT…` | `Thailand` | 2 | 0 | 1.0 |
| `APAC - THN - Retail IT…` | `THN` | 1 | 0 | 1.0 |
| `APAC - THN - Retail IT…` | `POS` | 25 | 0 | 1.0 |
| `APAC - THN - Retail IT…` | `point of sale` | 0 | 0 |  |
| `APAC - THN - Retail IT…` | `retail store` | 1 | 0 | 1.0 |
| `APAC - THN - Retail IT…` | `in-store` | 0 | 0 |  |
| `APAC - THN - Retail IT…` | `cashier` | 0 | 0 |  |
| `APAC - THN - Retail IT…` | `terminal` | 0 | 0 |  |
| `APAC - THN - Retail IT…` | `store network` | 0 | 0 |  |
| `APAC - THN - Retail IT…` | `printer` | 0 | 0 |  |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `iBeauty` | 15 | 0 | 1.0 |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `beauty advisor` | 0 | 0 |  |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `BA` | 56 | 0 | 1.0 |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `in-store app` | 0 | 0 |  |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `clienteling` | 0 | 0 |  |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `advisor app` | 0 | 0 |  |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `consultation` | 0 | 0 |  |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `skin` | 2 | 0 | 1.0 |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `shade` | 0 | 0 |  |
| `APAC - ZN - iBeauty 2.0 - Retail - L2…` | `retail app` | 1 | 0 | 1.0 |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `OMNISALES` | 1 | 0 | 1.0 |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `omni` | 2 | 0 | 1.0 |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `MARS` | 47 | 0 | 1.0 |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `Capgemini` | 30 | 0 | 1.0 |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `GDC` | 1 | 0 | 1.0 |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `click and collect` | 0 | 0 |  |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `ship from store` | 0 | 0 |  |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `inventory` | 0 | 0 |  |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `retail order` | 0 | 0 |  |
| `APAC - ZN - O+O OMNISALES.RETAIL - CAPGE…` | `MARS integration` | 0 | 0 |  |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `CED` | 9 | 0 | 1.0 |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `e-commerce` | 0 | 0 |  |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `online` | 1 | 0 | 1.0 |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `web order` | 0 | 0 |  |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `cart` | 0 | 0 |  |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `checkout` | 0 | 0 |  |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `SPACE GDS` | 0 | 0 |  |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `online store` | 0 | 0 |  |
| `APAC - ZN - O+O ONLINE.CED - CAPGEMINI-G…` | `SPACE-GDS` | 0 | 0 |  |
| `APAC - ZN - O+O.CRM - L2…` | `CRM` | 28 | 0 | 1.0 |
| `APAC - ZN - O+O.CRM - L2…` | `loyalty` | 24 | 0 | 1.0 |
| `APAC - ZN - O+O.CRM - L2…` | `consumer profile` | 4 | 0 | 1.0 |
| `APAC - ZN - O+O.CRM - L2…` | `lucid` | 37 | 0 | 1.0 |
| `APAC - ZN - O+O.CRM - L2…` | `registration` | 3 | 0 | 1.0 |
| `APAC - ZN - O+O.CRM - L2…` | `account` | 17 | 0 | 1.0 |
| `APAC - ZN - O+O.CRM - L2…` | `consent` | 0 | 0 |  |
| `APAC - ZN - O+O.CRM - L2…` | `GDPR` | 0 | 0 |  |
| `APAC - ZN - O+O.CRM - L2…` | `Salesforce` | 0 | 0 |  |
| `APAC - ZN - O+O.CRM - L2…` | `marketing` | 2 | 0 | 1.0 |
| `APAC - ZN - O+O.CRM - L2…` | `email campaign` | 0 | 0 |  |
| `APAC - ZN - O+O.NGLORA - L2…` | `NGLORA` | 0 | 0 |  |
| `APAC - ZN - O+O.NGLORA - L2…` | `LORA` | 0 | 0 |  |
| `APAC - ZN - O+O.NGLORA - L2…` | `ORA` | 8 | 0 | 1.0 |
| `APAC - ZN - O+O.NGLORA - L2…` | `loyalty rewards` | 0 | 0 |  |
| `APAC - ZN - O+O.NGLORA - L2…` | `points` | 18 | 0 | 1.0 |
| `APAC - ZN - O+O.NGLORA - L2…` | `tier` | 2 | 0 | 1.0 |
| `APAC - ZN - O+O.NGLORA - L2…` | `redemption` | 1 | 0 | 1.0 |
| `APAC - ZN - O+O.NGLORA - L2…` | `rewards programme` | 0 | 0 |  |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `operations` | 1 | 0 | 1.0 |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `ops` | 3 | 0 | 1.0 |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `batch` | 13 | 0 | 1.0 |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `ETL` | 3 | 0 | 1.0 |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `pipeline` | 1 | 0 | 1.0 |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `data sync` | 0 | 0 |  |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `integration` | 2 | 0 | 1.0 |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `API` | 47 | 0 | 1.0 |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `webhook` | 0 | 0 |  |
| `APAC - ZN - O+O.OPERATIONS - L2…` | `data ingestion` | 0 | 0 |  |
| `APAC - ZN - SPACE B2C Hypercare…` | `hypercare` | 12 | 8 | 0.33 |
| `APAC - ZN - SPACE B2C Hypercare…` | `go live` | 2 | 1 | 0.5 |
| `APAC - ZN - SPACE B2C Hypercare…` | `go-live` | 4 | 0 | 1.0 |
| `APAC - ZN - SPACE B2C Hypercare…` | `launch` | 3 | 1 | 0.67 |
| `APAC - ZN - SPACE B2C Hypercare…` | `cutover` | 0 | 0 |  |
| `APAC - ZN - SPACE B2C Hypercare…` | `P1` | 0 | 0 |  |
| `APAC - ZN - SPACE B2C Hypercare…` | `escalation` | 0 | 0 |  |
| `APAC - ZN - SPACE B2C Hypercare…` | `new market` | 0 | 0 |  |
| `APAC - ZN - SPACE B2C Hypercare…` | `B2C` | 13 | 5 | 0.62 |
| `APAC - ZN - SPACE B2C Hypercare…` | `regression` | 0 | 0 |  |
| `APAC - ZN - SPACE B2C Hypercare…` | `critical` | 1 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `infrastructure` | 1 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `HIP` | 15 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `platform` | 3 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `cloud` | 3 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `server` | 18 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `network` | 0 | 0 |  |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `certificate` | 0 | 0 |  |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `SSL` | 1 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `DNS` | 0 | 0 |  |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `database` | 12 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `auth` | 2 | 0 | 1.0 |
| `TECH FNDN - WW - HIP INCIDENT L2…` | `SSO` | 8 | 0 | 1.0 |

¹ Drift = `1 - (in_group / total)` — i.e. the fraction of matches that landed in a **different** current group. High drift means the keyword is ambiguous.

