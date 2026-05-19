# Re-score of 64 quick-018 incidents under v1.1 rules

Re-ran `recommend_assignment` against the same 64 incidents fetched in quick-018.
This calls the actual production function so the result reflects the real code path.

## Headline

| Rules version | Match rate (current = recommended) |
|---|---:|
| v1.0 (quick-018 baseline) | 11/64 = 17.2 % |
| v1.1 (this rewrite)       | 20/64 = 31.2 % |

**Delta: +9 incidents** (absolute), +14.1 pp.

## Per-incident comparison

| # | Incident | Short Description | Current | v1.1 Recommended | Conf | Match? |
|---|---|---|---|---|---:|:---:|
| 1 | `INC10413436` | SG, MY, HK, JP \| All Brands \| GetCustomerById, GetPurchaseV2 , GetCalculatedAttr | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.75 | ✗ |
| 2 | `INC10419095` | MY , SG \| YSL, kiehls \|  POST Customer/GetCustomerById [v] API failure | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.667 | ✓ |
| 3 | `INC10487330` | ANZ \| Campaign data missing from Campaigns table. Broken campaign target/respons | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.286 | ✓ |
| 4 | `INC10387135` | P2 Alert received due to FindConsumerProfile failure with 504 error | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.714 | ✓ |
| 5 | `INC10328738` | MY/KIE- After migration both ID found under prospect and couldn't found in MARs  | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.5 | ✓ |
| 6 | `INC10482324` | [RETAIL] : iBeauty 2.0 - APAC: Unable to search customer details | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.5 | ✓ |
| 7 | `INC10453163` | ID SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.833 | ✓ |
| 8 | `INC10462256` | TH SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.833 | ✓ |
| 9 | `INC10462212` | MY SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.75 | ✓ |
| 10 | `INC10450026` | CDS Infrastructure - CloudSQL not syncing data to Replica | SGP - SPACE CDS SAPMENA L2 Support | WW - HIP INCIDENT L2 | 0.75 | ✗ |
| 11 | `INC10367950` | MTY\| LAN \|Customer Purchase on member days 29/3/26 RM4510 x 3points= 13530 point | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.333 | ✗ |
| 12 | `INC10312845` | SG/KIE-This member account can't find in MARS and also his personal details on t | SGP - SPACE CDS SAPMENA L3 Support | ZN - SPACE B2C Hypercare | 0.5 | ✗ |
| 13 | `INC10293500` | [MARS-ANZ] Sales representative does not exist | SGP - SPACE CDS SAPMENA L2 Support | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | 0.417 | ✗ |
| 14 | `INC10457408` | ANZ \| Patching locationid and salesrepid in AESOP | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.25 | ✗ |
| 15 | `INC10431241` | TH Generic Tourist Others Profile closed | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.5 | ✗ |
| 16 | `INC10429906` | Failed to insert batch into stg_sap_product_hierarchy: numeric field overflow | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.75 | ✗ |
| 17 | `INC10304697` | CRM Lite brands not migrated with accurate last update date from SFMC resulting  | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.6 | ✗ |
| 18 | `INC10320937` | SG/YSL-The points has not been reflected in membership account. | SGP - SPACE CDS SAPMENA L3 Support | ZN - SPACE B2C Hypercare | 0.444 | ✗ |
| 19 | `INC10483228` | ANZ \| Invalid SFMC Prospects Ingested | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.75 | ✓ |
| 20 | `INC10231059` | TH ALL-R12M purchase amount is always not showing on Ibeauty. | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.333 | ✓ |
| 21 | `INC10430912` | MY/LAN-Rebind the order to the correct LUCID. | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 0.286 | ✗ |
| 22 | `INC10420625` | AUS \| KER \| customer has no records on account 288560 | ZN - SPACE B2C Hypercare | ZN - SPACE B2C Hypercare | 0.5 | ✓ |
| 23 | `INC10381009` | MY/KIE-To seek clarify on the point adjustment appear in the point history page. | ZN - SPACE B2C Hypercare | ZN - SPACE B2C Hypercare | 0.667 | ✓ |
| 24 | `INC10466783` | [LCM] Request for Deletion of Loyalty Account Data SFDC: 01326210 | CHN - SPACE Loyalty L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.333 | ✗ |
| 25 | `INC10471722` | MY/KIE-Please help activate the customer's account. | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.667 | ✗ |
| 26 | `INC10142664` | SG \| KIE \| UNABLE TO MERGE DUPLICATE ACCOUNT | ZN - SPACE B2C Hypercare | ZN - O+O.CRM - L2 | 0.5 | ✗ |
| 27 | `INC10449165` | TH Lancome Customer profile closed and not earn points | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.25 | ✗ |
| 28 | `INC10394746` | TH \| LAN \| Duplicated Mar ID | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.333 | ✗ |
| 29 | `INC10199563` | [E2E TESTING] TH YSL- Account registered via EBTQ shows incorrect creation count | ZN - SPACE B2C Hypercare | ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2 | 0.263 | ✗ |
| 30 | `INC10475182` | SFMC Prospect Ingestion incorrectly updating sourceLastUpdatedDatetime to curren | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.8 | ✓ |
| 31 | `INC10384818` | Please check customer with phone number in Kiehl's | SGP - SPACE CDS SAPMENA L2 Support | ZN - O+O.CRM - L2 | 0.375 | ✗ |
| 32 | `INC10377206` | VN SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.444 | ✓ |
| 33 | `INC10421600` | CDS Consumer Registration - Default Optins to include SMS for SG, MY, TH | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.571 | ✗ |
| 34 | `INC10080190` | MY \| GAB \| Profile different between iBeauty and MARS | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.286 | ✗ |
| 35 | `INC10442394` | E2E Monitoring \| SAPMENA PRD \| All Brands \| SFCC -> CDS Missing Order APR | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.6 | ✗ |
| 36 | `INC10422037` | MY-LAN:customer account could not be found in SPACE | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 0.333 | ✗ |
| 37 | `INC10466356` | API Issue \|\| Cloudfare error from Arvato endpoint for multiple exchanges across  | CHN - SPACE Loyalty L3 Support | WW - HIP INCIDENT L2 | 0.444 | ✗ |
| 38 | `INC10209070` | ID \| KIE \| Customer cannot be found in iBeauty despite being registered in MARS | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 0.444 | ✗ |
| 39 | `INC10228919` | ID \| Customer service mentioned that they could not find the customer's informat | ZN - SPACE B2C Hypercare | ZN - SPACE B2C Hypercare | 0.5 | ✓ |
| 40 | `INC10453953` | MY/KIE-Historical points have not been credited. | ZN - SPACE B2C Hypercare | ZN - SPACE B2C Hypercare | 0.5 | ✓ |
| 41 | `INC10343465` | MY/KIE-Order and points have not been credited. | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 1.0 | ✗ |
| 42 | `INC10315765` | UT-O: [MARS-ANZ] CRM Customer in rejections | ZN - SPACE B2C Hypercare | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | 0.375 | ✗ |
| 43 | `INC10297852` | MY/KIE-The order and the corresponding points have not been recorded. | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 0.375 | ✗ |
| 44 | `INC10166077` | \|TH\| \|YSL\| Missing Order Issue: Discrepancy between MARS and SPACE LOYALTY regar | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 0.286 | ✗ |
| 45 | `INC10462250` | SG SPACE - Outbound Gap Data to MARS | SGP - SPACE CDS SAPMENA L2 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.833 | ✓ |
| 46 | `INC10395005` | SG\|YSL\|Birthday Call List | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.667 | ✗ |
| 47 | `INC10378086` | Master Data Cleanup for Kiehls / Lancome | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.5 | ✗ |
| 48 | `INC10439424` | FirstTransactionXXX Tags have wrong value | CHN - SPACE Loyalty L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.5 | ✗ |
| 49 | `INC10415946` | MY \| KIE \| Members' Points not Reflection in iBeauty (2nd Raise) | ZN - SPACE B2C Hypercare | ZN - SPACE B2C Hypercare | 0.385 | ✓ |
| 50 | `INC10284821` | TH All Brands : Incorrect Lucid and Mars ID in C360 | SGP - SPACE CDS SAPMENA L3 Support | ZN - SPACE B2C Hypercare | 0.6 | ✗ |
| 51 | `INC10429974` | Receipt Query - Wrong Brand Name for Shu ION | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.5 | ✗ |
| 52 | `INC10301307` | E2E monitoring \| JP PRD  \| CDS vs LOY Same MarsId with different Lucid-0301-0314 | CHN - SPACE Loyalty L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.556 | ✗ |
| 53 | `INC10367251` | RITM7405487 \| E2E Monitoring \| TH, ID PRD\| All Brands \| LOY -> Recon Dashboard ( | CHN - SPACE Loyalty L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.75 | ✗ |
| 54 | `INC10190808` | TH \| LAN \| Creation counter missing on C360 | ZN - SPACE B2C Hypercare | ZN - SPACE B2C Hypercare | 0.5 | ✓ |
| 55 | `INC10324255` | [MARS-VN,ID] Customer in rejections | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 0.333 | ✗ |
| 56 | `INC10081673` | TH Tourist Others customer type to fix | SGP - SPACE CDS SAPMENA L3 Support | ZN - SPACE B2C Hypercare | 0.455 | ✗ |
| 57 | `INC10310154` | TH YSL Other Tourist code keeps closed | SGP - SPACE CDS SAPMENA L3 Support | ZN - SPACE B2C Hypercare | 0.4 | ✗ |
| 58 | `INC10300640` | TH KIE Local Generic code issue | SGP - SPACE CDS SAPMENA L3 Support | SGP - SPACE CDS SAPMENA L2 Support | 1.0 | ✗ |
| 59 | `INC10396182` | CAPLINERR003-Linux Host-HKAPACLOYAPD2A FS /mnt/aupd usage above 90 in last 10 mi | CHN - SPACE Loyalty L3 Support | WW - HIP INCIDENT L2 | 1.0 | ✗ |
| 60 | `INC10114698` | Indonesia: None of the orders coming into LOY eventhough status is delivered | ZN - SPACE B2C Hypercare | ZN - SPACE B2C Hypercare | 0.5 | ✓ |
| 61 | `INC10403825` | SHU JP Returned Order – Rule-500 AR Subscription Points Not Reversed | CHN - SPACE Loyalty L3 Support | ZN - O+O.NGLORA - L2 | 0.667 | ✗ |
| 62 | `INC10204372` | [MARS-MY], [MARS-TH] [MARS-SG] CRM Customer in rejections | ZN - SPACE B2C Hypercare | ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | 0.4 | ✗ |
| 63 | `INC10190032` | E2E Monitoring \| SG Prod \| All Brands \| Missing Orders 0101-0131 MARS channel fo | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 0.667 | ✗ |
| 64 | `INC10282648` | RITM7326831 \| MY\|YSL\|Customer Loyalty Redemption Trends & Product Performance | ZN - SPACE B2C Hypercare | SGP - SPACE CDS SAPMENA L2 Support | 0.5 | ✗ |

## Match rate by current group

| Current Group | Incidents | Matched | Rate |
|---|---:|---:|---:|
| SGP - SPACE CDS SAPMENA L3 Support | 22 | 0 | 0.0 % |
| ZN - SPACE B2C Hypercare | 19 | 7 | 36.8 % |
| SGP - SPACE CDS SAPMENA L2 Support | 16 | 13 | 81.2 % |
| CHN - SPACE Loyalty L3 Support | 7 | 0 | 0.0 % |

## Where the 44 v1.1 mispredictions land

| Predicted Group | Count |
|---|---:|
| SGP - SPACE CDS SAPMENA L2 Support | 29 |
| ZN - SPACE B2C Hypercare | 5 |
| WW - HIP INCIDENT L2 | 3 |
| ZN - O+O OMNISALES.RETAIL - CAPGEMINI-GDC-MARS - RUN - L2 | 3 |
| ZN - O+O.CRM - L2 | 2 |
| ZN - O+O ONLINE.CED - CAPGEMINI-GDC-SPACE-GDS - RUN - L2 | 1 |
| ZN - O+O.NGLORA - L2 | 1 |

