import json
import csv
import pandas as pd
import openpyxl

# Specify the path to your JSON file
base_path = '/home/markus/Malabio/PDBminer/results/'
protein = 'Q5S007'
name = "LRRK2_HUMAN"
mutations = ["G2019S", "R1441G", "R1441C", "R1441H", "Y1699C", "I2020T", "I2020K", "G2385R"]
json_file = base_path + protein + "/" + protein + "_all.json"

# Open the JSON file and load the data
with open(json_file) as file:
    data = json.load(file)

data_df = {"structure_ids":[],
           "deposition_date":[],
           "experimental_method":[],
           "complex_protein_details":[],
           "complex_ligand_details":[],
           "mutations_in_protein":[],
           "mutation_ordering":[],
           "other_mutations":[],
           "resolution":[],
           "coverage":[],
           "warnings":[],}

for i in data["chains"].keys():
    complex_protein_details = data["complex_protein_details"][i]
    if complex_protein_details == "NA":
        protein_chain = data["chains"][i][0]
    else:
        complex_string = complex_protein_details[0].split(";")
        for j in complex_string:
            if name in j:
                protein_chain = j[-1]
    if data["mutations_in_pdb"][i] == "NA":
        protein_mutations = "NA"
    else:
        protein_mutations = data["mutations_in_pdb"][i][protein_chain]
    mutation_ordering = "NA"
    if not protein_mutations == "NA":
        for j, m in enumerate(mutations):
            for k in protein_mutations:
                if m in k and mutation_ordering == "NA":
                    mutation_ordering = j
    else:
        mutation_ordering = len(mutations)
    if data["mutations_in_pdb"][i] == "NA":
        other_mutations = "NA"
    else:
        other_mutations = {j:data["mutations_in_pdb"][i][j] for j in data["mutations_in_pdb"][i].keys() if j != protein_chain}
    pdb_chains = data["complex_protein_details"][i]
    complex_ligand_details = data["complex_ligand_details"][i]
    structure_id = data["structure_id"][i]
    deposition_date = data["deposition_date"][i]
    experimental_method = data["experimental_method"][i]
    resolution = data["resolution"][i]
    coverage = data["coverage"][i]
    warnings = data["warnings"][i]

    data_df["structure_ids"].append(structure_id)
    data_df["deposition_date"].append(deposition_date)
    data_df["experimental_method"].append(experimental_method)
    data_df["complex_protein_details"].append(complex_protein_details)
    data_df["complex_ligand_details"].append(complex_ligand_details)
    data_df["mutations_in_protein"].append(protein_mutations)
    data_df["other_mutations"].append(other_mutations)
    data_df["mutation_ordering"].append(mutation_ordering)
    data_df["resolution"].append(resolution)
    data_df["coverage"].append(coverage)
    data_df["warnings"].append(warnings)

data_df = pd.DataFrame(data_df)
data_df["mutation_ordering"][data_df["mutation_ordering"] == "NA"] = len(mutations) + 1
data_df["mutation_ordering"] = data_df["mutation_ordering"].astype(int)
data_df = data_df.sort_values(by=["mutation_ordering", "deposition_date"], ascending=[True, False])

data_df.to_csv(base_path + protein + "/" + protein + "_all.csv", index=False, sep=";")

#To excel
data_df.to_excel(base_path + protein + "/" + protein + "_all.xlsx")


print("Table successfully exported as CSV.")