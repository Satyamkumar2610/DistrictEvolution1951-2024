# District Lineage & Evolution Graph Design

This document extracts the implicit district lineage knowledge embedded within the two ICRISAT datasets (Historical/Apportioned vs. Modern/Unapportioned).

## 1. Graph Data Model Design

To formally map district evolution over time, the system should adopt a Directed Acyclic Graph (DAG) architecture.

### Node (District Snapshot)
- `id`: Unique composite key (e.g., `TG_Adilabad_2016`)
- `name`: District Name
- `state`: State Name
- `system_type`: `APPORTIONED` (Historical) | `UNAPPORTIONED` (Modern)
- `valid_from`: First appearance year in dataset
- `valid_to`: Last appearance year in dataset
- `confidence`: Data quality score based on reporting frequency

### Edge (Lineage Event)
- `source_node`: Parent District ID
- `target_node`: Child District ID
- `event_type`: `IDENTITY` | `SPLIT` | `STATE_REORG` | `NAME_CHANGE`
- `event_year`: Year the change occurred

## 2. Extracted Lineage Intelligence

### Telangana
**Historical Parents (Apportioned System):** 10  
**Modern Children (Unapportioned System):** 33

#### Evolution Chains:
- **Kurnool** (1966-2017) ➔ **Nagarkurnool** (2016-2019) `[IDENTITY]`
- **Hyderabad** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Hyderabad** (1990-2014)
  - ↳ **Malkaigiri** (2016-2019)
- **Nizamabad** (1966-2017) ➔ **Nizamabad** (1990-2019) `[IDENTITY]`
- **Medak** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Medak** (1990-2019)
  - ↳ **Kamareddy** (2016-2019)
  - ↳ **Sangareddy** (2016-2019)
  - ↳ **Siddipet** (2016-2019)
- **Mahabubnagar** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Mahabubnagar** (1990-2019)
  - ↳ **Jogulamba** (2016-2019)
  - ↳ **Nagarkurnool** (2016-2019)
  - ↳ **Wanaparthy** (2016-2019)
  - ↳ **Narayanpet** (2018-2019)
- **Nalgonda** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Nalgonda** (1990-2019)
  - ↳ **Suryapet** (2016-2019)
  - ↳ **Yadadri Bhuvanagiri** (2016-2019)
- **Warangal** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Warangal** (1990-2019)
  - ↳ **Janagaon** (2016-2019)
  - ↳ **Jayashankar Bhuppaly** (2016-2019)
  - ↳ **Mahabubabad** (2016-2019)
  - ↳ **Warangal Urban** (2016-2019)
  - ↳ **Mulugu** (2018-2019)
- **Khammam** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Khammam** (1990-2019)
  - ↳ **Bhadradri** (2016-2019)
- **Karimnagar** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Karimnagar** (1990-2019)
  - ↳ **Jagityal** (2016-2019)
  - ↳ **Peddapally** (2016-2019)
  - ↳ **Rajanna Siricilla** (2016-2019)
- **Adilabad** (1966-2017) ➔ `[SPLIT]`
  - ↳ **Adilabad** (1990-2019)
  - ↳ **Kumurambheem Asifabad** (2016-2019)
  - ↳ **Macherial** (2016-2019)
  - ↳ **Nirmal** (2016-2019)

---
### Andhra Pradesh
**Historical Parents (Apportioned System):** 11  
**Modern Children (Unapportioned System):** 13

#### Evolution Chains:
- **Srikakulam** (1966-2017) ➔ **Srikakulam** (1990-2019) `[IDENTITY]`
- **Visakhapatnam** (1966-2017) ➔ **Visakhapatnam** (1990-2019) `[IDENTITY]`
- **East Godavari** (1966-2017) ➔ **East Godavari** (1990-2019) `[IDENTITY]`
- **West Godavari** (1966-2017) ➔ **West Godavari** (1990-2019) `[IDENTITY]`
- **Krishna** (1966-2017) ➔ **Krishna** (1990-2019) `[IDENTITY]`
- **Guntur** (1966-2017) ➔ **Guntur** (1990-2019) `[IDENTITY]`
- **S.P.S. Nellore** (1966-2017) ➔ **S.P.S.Nellore** (1990-2019) `[IDENTITY]`
- **Kurnool** (1966-2017) ➔ **Kurnool** (1990-2019) `[IDENTITY]`
- **Ananthapur** (1966-2017) ➔ **Anantapur** (1990-2019) `[IDENTITY]`
- **Kadapa YSR** (1966-2017) ➔ **Kadapa YSR** (1990-2019) `[IDENTITY]`
- **Chittoor** (1966-2017) ➔ **Chittoor** (1990-2019) `[IDENTITY]`

---
### Chhattisgarh
**Historical Parents (Apportioned System):** 6  
**Modern Children (Unapportioned System):** 28

#### Evolution Chains:
- **Durg** (1966-2017) ➔ **Durg** (1990-2019) `[IDENTITY]`
- **Bastar** (1966-2017) ➔ **Bastar** (1990-2019) `[IDENTITY]`
- **Raipur** (1966-2017) ➔ **Raipur** (1990-2019) `[IDENTITY]`
- **Bilaspur** (1966-2017) ➔ **Bilaspur** (1990-2019) `[IDENTITY]`
- **Raigarh** (1966-2017) ➔ **Raigarh** (1990-2019) `[IDENTITY]`
- **Surguja** (1966-2017) ➔ **Surguja** (1990-2019) `[IDENTITY]`

---
### Jharkhand
**Historical Parents (Apportioned System):** 6  
**Modern Children (Unapportioned System):** 24

#### Evolution Chains:
- **Santhal Paragana / Dumka** (1966-2017) ➔ **Santhal Paragana Dumka** (1990-2019) `[IDENTITY]`
- **Hazaribagh** (1966-2017) ➔ **Hazaribagh** (1990-2019) `[IDENTITY]`
- **Dhanbad** (1966-2017) ➔ **Dhanbad** (1990-2019) `[IDENTITY]`
- **Palamau** (1966-2017) ➔ **Palamau** (1990-2019) `[IDENTITY]`
- **Ranchi** (1966-2017) ➔ **Ranchi** (1990-2019) `[IDENTITY]`
- **Singhbhum** (1966-2017) ➔ *(No mapped modern children)*

---
### Uttarakhand
**Historical Parents (Apportioned System):** 8  
**Modern Children (Unapportioned System):** 13

#### Evolution Chains:
- **Nainital** (1966-2017) ➔ **Nainital** (1990-2019) `[IDENTITY]`
- **Almorah** (1966-2017) ➔ **Almorah** (1990-2019) `[IDENTITY]`
- **Pithorgarh** (1966-2017) ➔ **Pithorgarh** (1990-2019) `[IDENTITY]`
- **Chamoli** (1966-2017) ➔ **Chamoli** (1990-2019) `[IDENTITY]`
- **Uttar Kashi** (1966-2017) ➔ **Uttar Kashi** (1990-2019) `[IDENTITY]`
- **Tehri Garhwal** (1966-2017) ➔ **Tehri Garhwal** (1990-2019) `[IDENTITY]`
- **Garhwal** (1966-2017) ➔ **Garhwal** (1990-2019) `[IDENTITY]`
- **Dehradun** (1966-2017) ➔ **Dehradun** (1990-2019) `[IDENTITY]`
