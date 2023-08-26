#!/usr/bin/env python

# PDBminer_functions: classes and functions for PDBminer_run.py
# Copyright (C) 2022, Kristine Degn
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


#============================================================================#
#Importing relevant packages
#============================================================================#
import os
import pandas as pd
import requests
import json
import itertools
import numpy as np
from Bio.PDB import *
from Bio import pairwise2
from Bio import SeqIO
from io import StringIO
from biopandas.pdb import PandasPdb
from Bio.SeqUtils import seq1
from Bio import PDB
from requests.exceptions import ConnectionError

#============================================================================#
# Following the Documentation from PDBminer_run.py
# Step 1 - import is done in PDBminer_run
#============================================================================#

#============================================================================#
# 2)  find all structures related to the uniprot id 
#============================================================================#
# This step consist of four functions. 
#
#   get(pdbs)
#   get_structure_metadata(pdb_id)
#   get_structure_df(uniprot_id)
#   get_alphafold_basics(uniprot_id)
#   find_structure_list(input_dataframe)
#
#   The functions are called through find_structure_list
#   the aim is to take the input dataframe as input and output
#   a dataframe "found_structure_list" with all avialable PDB & newest AF 
#   structure including their metadata for further analysis. 

def get_alphafold_basics(uniprot_id):
    print(f"FUNCTION: get_alphafold_basics({uniprot_id})")
    """
    Function that takes a uniprot id and retrieve data from the alphafold
    database, and prepare the basic information of that model in alignment 
    with the PDB data.

    Parameters
    ----------
    uniprot_id : A sting, e.g. 'P04637'

    Returns
    -------
    A tuple of information fitting as a line in the structure_df captured 
    in get_structure_df. 

    """
    
    try: 
        response = requests.get(f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}")
    except ConnectionError as e:
        with open("log.txt", "a") as textfile:
            textfile.write(f"EXITING: AlphaFold database API controlled and rejected for {uniprot_id}, connection error.\n")
        exit(1)
    
    if response.status_code == 200:
        result = response.json()[0]
        deposition_date = result['modelCreatedDate'] 
        Alphafold_ID = result['pdbUrl'].split('/')[-1][:-4]

        return Alphafold_ID, uniprot_id, deposition_date, "PREDICTED", "NA", 0
    
    else:
        with open("log.txt", "a") as textfile:
            textfile.write(f"WARNING: The Alphafold Database returned an error for the request of {uniprot_id}.\n")
        return

    
def get_pdbs(uniprot_id):
    print(f"FUNCTION: get_pdbs({uniprot_id})")
    """
    Function is taken from SLiMfast, documentation and comments there.
    Credit: Valentina Sora
    
    """
    try: 
        response = requests.get(f"https://www.uniprot.org/uniprot/{uniprot_id}.txt")
    except ConnectionError as e:
        with open("log.txt", "a") as textfile:
            textfile.write(f"EXITING: Uniprot database API controlled and rejected for {uniprot_id}, connection error. \n")
        exit(1) 
    
    if response.status_code == 200:

        pdbs = []
        
        for line in response.text.split("\n"):
            
            if line.startswith("DR   PDB;"):
                
                db, pdb_id, exp, res, chain_res = \
                    [item.strip(" ") for item \
                     in line.rstrip(".\n").split(";")]
                
                pdbs.append(pdb_id)
    
        return pdbs
    
    else:
        with open("log.txt", "a") as textfile:
            textfile.write(f"WARNING: The Uniprot Database returned an error for the request of {uniprot_id}.\n")

def get_structure_metadata(pdb_id):
    print(f"FUNCTION: get_structure_metadata({pdb_id})")
    
    """
    Function that takes each pdb_id and retrive metadata from the PDBe.
    The metadata consist of desposition date to the PDB, the experimental
    metod used to solve the structure and the resolution if reported. 

    Parameters
    ----------
    pdb_id : four letter code defining a structure reported in the protein 
             data bank.

    Returns
    -------
    A tuple of metadata: deposition_date, experimental_method, resolution

    """
    
    try: 
        response = requests.get(f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/summary/{pdb_id}")
    except ConnectionError as e:
        with open("log.txt", "a") as textfile:
            textfile.write(f"EXITING: PDBe database API controlled and rejected for {pdb_id}, connection error. \n")
        exit(1) 
    
    if response.status_code != 200:
        return
    
    response_text = json.loads(response.text)
    dictionary = response_text[pdb_id.lower()]
    dictionary = dictionary[0]

    #Change the date format
    deposition_date = f"{dictionary['deposition_date'][:4]}-{dictionary['deposition_date'][4:6]}-{dictionary['deposition_date'][6:]}"
    #Find the experimental method
    experimental_method = str(dictionary['experimental_method'][0]).upper()
    
    #Retrieve information regarding resolution
    
    #exlude NMR structures (all NMR types)
    if "NMR" in experimental_method:
        
        resolution = "NA"
        #Would be nice to have ResProx here, but there is not an API.
    
    #include all others
    else:
        try: 
            response_experiment = requests.get(f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/experiment/{pdb_id}")
        except ConnectionError as e:
            with open("log.txt", "a") as textfile:
                textfile.write(f"EXITING: PDB database API (experiments) controlled and rejected for {pdb_id}, connection error. \n")
            exit(1) 
        
        if response_experiment.status_code != 200:
            return

        response_text_exp = json.loads(response_experiment.text)
        dictionary_exp = response_text_exp[pdb_id.lower()]
        dictionary_exp = dictionary_exp[0]
        resolution = dictionary_exp['resolution']
    
    return deposition_date, experimental_method, resolution

def get_PDBredo(pdb):
    print(f"FUNCTION: get_PDBredo({pdb})")
    """

    Parameters
    ----------
    pdb : four letter PDB code.

    Returns
    -------
    str: YES/NO for availability in PDB-REDO database.
    rfree_improve: a string detailing the orignal and PDBredo r-free values, "NA" if non applicable
    """
    
    try: 
        response = requests.get(f"https://pdb-redo.eu/db/{pdb}/data.json")
    except ConnectionError as e:
        with open("log.txt", "a") as textfile:
            textfile.write(f"EXITING: PDB-REDO database API controlled and rejected for {pdb_id}, connection error. \n")
        exit(1) 
    
    if response.status_code == 200: 
        response_data = response.json()
        r_free_pdbredo = response_data['properties']['RFFIN']
        return "YES", r_free_pdbredo
    else:
        return "NO", "NA"
    

def get_structure_df(uniprot_id): 
    """
    This function takes a single uniprot ID and outputs a 
    dataframe containing a sorted list of PDB ids and their metadata. 

    Parameters
    ----------
    uniprot_id : A sting, e.g. 'P04637'

    Returns
    -------
    structure_df :  A pandas dataframe containing all the names and details
                    regarding the solved structures related to the 
                    uniprot id in terms of pdb files.  

    """
    
    print(f"FUNCTION: get_structure_df({uniprot_id})")
    
    try: 
        response = requests.get(f"https://www.ebi.ac.uk/pdbe/pdbe-kb/3dbeacons/api/uniprot/{uniprot_id}.json?provider=pdbe")
    except ConnectionError as e:
        with open("log.txt", "a") as textfile:
            textfile.write("EXITING: 3D-Beacons database API controlled and rejected, connection error.\n")
        #print("3D-Beacons database API controlled and rejected, connection error\n")
        exit(1) 
    
    if response.status_code != 200:
        with open("log.txt", "a") as textfile:
            textfile.write(f"WARNING: 3D-Beacons did not return any PDBe structures for {uniprot_id}.\n")
        pdbs = get_pdbs(uniprot_id)
        
        if len(pdbs) != 0:
            with open("log.txt", "a") as textfile:
                textfile.write(f"WARNING: Uniprot returned {len(pdbs)} structures. NOTICE that structures deposited in the PDB within 8 weeks may not be included in this list.\n")
            
            pdb = []
            deposition_date = []
            experimental_method = [] 
            resolution = []
            
            for pdb_id in pdbs:
                metadata = get_structure_metadata(pdb_id)

                if metadata is None:
                    textfile.write(f"WARNING: PDBe database API retured an error for {pdb_id}.\n")
                    return uniprot_id
            
                pdb.append(pdb_id)
                deposition_date.append(metadata[0])
                experimental_method.append(metadata[1]) 
                resolution.append(metadata[2])
            
            structure_df = pd.DataFrame({"pdb": pdb, 
                                         "uniprot_id": [uniprot_id]*len(pdb), 
                                         "deposition_date": deposition_date, 
                                         "experimental_method": experimental_method, 
                                         "resolution": resolution}) 
            
            rank_dict = {'X-RAY DIFFRACTION': 1,'ELECTRON MICROSCOPY': 2,'ELECTRON CRYSTALLOGRAPHY': 3,'SOLUTION NMR': 4, 'SOLID-STATE NMR': 5}
            
            structure_df['method_priority'] = structure_df['experimental_method'].map(rank_dict).fillna(6)
            
            AF_model = get_alphafold_basics(uniprot_id)
            
            if AF_model is not None:
                structure_df.loc[len(structure_df)] = tuple(AF_model)
                
            
            structure_df.sort_values(["method_priority", "resolution", "deposition_date"], ascending=[True, True, False], inplace=True)
            structure_df = structure_df.drop(['method_priority'], axis=1)
            
            structure_df['PDBREDOdb'] = structure_df.apply(lambda row: get_PDBredo(row['pdb']), axis=1)
            structure_df[['PDBREDOdb', 'PDBREDOdb_details']] = structure_df['PDBREDOdb'].apply(pd.Series)
            
            structure_df = structure_df.set_index('pdb')
            
        else:
            with open("log.txt", "a") as textfile:
                textfile.write(f"WARNING: Uniprot did not return any structures for {uniprot_id}.\n")
            AF_model = get_alphafold_basics(uniprot_id)
            if AF_model is None:
                textfile.write(f"WARNING: AlphaFold database returned an error for {uniprot_id}. This may indicate that there are no structure for {uniprot_id} in the Alphafold Database.\n")
                return uniprot_id
            
            structure_df = pd.DataFrame({'uniprot_id': [AF_model[1]], 
                                         'deposition_date': [AF_model[2]], 
                                         'experimental_method': [AF_model[3]], 
                                         'resolution': [AF_model[4]],
                                         'PDBREDOdb': "NO", 
                                         'PDBREDOdb_details': "NA"})
            structure_df.index = [AF_model[0]]           
        
        return structure_df

    else: 
        response_text = json.loads(response.text)
        structures = response_text['structures']
           
        pdb = []
        deposition_date = []
        experimental_method = [] 
        resolution = []
    
        for structure in structures:
            pdb.append(structure['summary']['model_identifier'].upper())
            deposition_date.append(structure['summary']['created'])
            experimental_method.append(structure['summary']['experimental_method'])
            resolution.append(structure['summary']['resolution'])

        structure_df = pd.DataFrame({"pdb": pdb, "uniprot_id": [uniprot_id]*len(pdb), "deposition_date": deposition_date, "experimental_method": experimental_method, "resolution": resolution})    
    
        rank_dict = {'X-RAY DIFFRACTION': 1,'ELECTRON MICROSCOPY': 2,'ELECTRON CRYSTALLOGRAPHY': 3,'SOLUTION NMR': 4, 'SOLID-STATE NMR': 5}
        
        structure_df['method_priority'] = structure_df['experimental_method'].map(rank_dict).fillna(6)
        
        AF_model = get_alphafold_basics(uniprot_id)
        
        if AF_model is not None:
            structure_df.loc[len(structure_df)] = tuple(AF_model)
        
        structure_df.sort_values(["method_priority", "resolution", "deposition_date"], ascending=[True, True, False], inplace=True)
        structure_df = structure_df.drop(['method_priority'], axis=1)
        
        structure_df['PDBREDOdb'] = structure_df.apply(lambda row: get_PDBredo(row['pdb']), axis=1)
        structure_df[['PDBREDOdb', 'PDBREDOdb_details']] = structure_df['PDBREDOdb'].apply(pd.Series)
        
        structure_df = structure_df.set_index('pdb')
                                                        
    return structure_df    

def find_structure_list(input_dataframe):  
    print("FUNCTION: find_structure_list(input_dataframe)")
    """
    Takes the input file and the path where it is placed and outputs
    a directory with a csv file for each uniprot id input and a txt file 
    including all the uniprot ids that does not have any solved structures.
    
    parameters
    ------------
    input_dataframe             The input df, as described in the readme file.  
    
    Returns          
    --------------
    missing_ID.txt:             Containing the uniprot id string which there 
                                are no solved structurs.
    
    found_structure_list:       A pandas datafrane where each solved structure
                                and a number of describtors are detailed. 
    """

    df_collector = []
    
    #take all uniprot id's from the input file
    all_uniprot_ids = list(input_dataframe.uniprot)
    all_uniprot_ids = sorted(set(all_uniprot_ids), key=all_uniprot_ids.index)
           
    for row in range(len(all_uniprot_ids)):
        
        print(all_uniprot_ids[row])
        
        structure_info = get_structure_df(all_uniprot_ids[row]) 
    
        if type(structure_info) != str: 
            df_collector.append(structure_info)
        
        else:
            with open("log.txt", "w") as textfile:
                textfile.write(f"No structures found in any resource for {structure_info}. \n")
            
    if len(df_collector) > 0:
        found_structure_list = pd.concat(df_collector) 
        
    else:
        found_structure_list = []
        
    return found_structure_list


#============================================================================#
# 3)  combine the input 1) and the structures 2)
#============================================================================#
# This step consist of one function. 
#
#   combine_structure_dfs(found_structures, input_dataframe)
#
#   The aim is to take the input dataframe, and the dataframe with all 
#   the structures from the prior step and combine these to a single 
#   dataframe to continue working on.


def combine_structure_dfs(found_structures, input_dataframe):
    print("FUNCTION: combine_structure_dfs(found_structures, input_dataframe)")
    """
    This function takes the found structures and the input dataframe
    and combine these for continues computation. 

    Parameters
    ----------
    found_structures : A pandas dataframe. 
    input_dataframe :  The original input dataframe with mutational information.

    Returns
    -------
    final_df :  A dataframe with nine columns including hugo_name, uniprot_id,
                uniprot_isoform, mutations, cluster_id, structure_id, deposition_date
                experimental_method, resolution

    """
    
    df_collector = []

    for i in range(len(input_dataframe)):
        sub_df = found_structures[found_structures.uniprot_id == input_dataframe.uniprot[i]]
        num_sub_df = len(sub_df)
        
        data = {
            "hugo_name": [input_dataframe.hugo_name[i]] * num_sub_df,
            "uniprot_id": [input_dataframe.uniprot[i]] * num_sub_df,
            "uniprot_isoform": [input_dataframe['uniprot_isoform'][i]] * num_sub_df,
            "mutations": [input_dataframe.mutations[i]] * num_sub_df,
            "cluster_id": [input_dataframe.cluster_id[i]] * num_sub_df,
            "structure_id": list(sub_df.index),
            "deposition_date": list(sub_df.deposition_date),
            "experimental_method": list(sub_df.experimental_method),
            "resolution": list(sub_df.resolution),
            "PDBREDOdb":list(sub_df.PDBREDOdb),
            "PDBREDOdb_rfree": list(sub_df.PDBREDOdb_details)
        }
        
        df_collector.append(pd.DataFrame(data))
    
    final_df = pd.concat(df_collector, ignore_index=True)
           
    return final_df

#============================================================================#
# 4)  For each sequence of structure (PDBid) an alignment to the fasta of 
#     the specified isoform. Here the differencies between the PDB and
#     fasta sequence is identified, the area of the sequence covered
#     by the PDB is annotated and the amino acids at the mutational sites
#     are found. NB! this does not account for quality of the structure. 
#============================================================================#
# This step consist of three functions. 
#
#   to_ranges(iterable)
#   align_uniprot_pdb(pdb_id, uniprot_id, isoform, mut_pos, path)
#   align_alphafold(alphafold_id, mutation_positions)
#   align(combined_structure, path)
#
#   The first functions is called by the second and the second and third 
#   function is called through the forth function.
#   The aim is to take the dataframe created in the prior step, and the 
#   relative path as input, and output an identical dataframe including 
#   information of structural coverage and amino acids in mutational sites.
#

def to_ranges(iterable):
    print("FUNCTION: to_ranges(iterable)")
    """
    Function to make each mutational group iterable, called to make a range
    interable.

    Parameters
    ----------
    iterable : a range of numbers e.g. (1, 10)

    """

    iterable = sorted(set(iterable))
    for key, group in itertools.groupby(enumerate(iterable),
                                        lambda t: t[1] - t[0]):
        group = list(group)
        yield group[0][1], group[-1][1]
        
def alignment(uniprot_sequence, AA_pdb):
    print("FUNCTION: alignment(uniprot_sequence, AA_pdb)")
    #1) Local alignment: Aim to find the area of the uniprot
    #   sequence the PDB covers.
    #2) Match (identical amino acids) =  1 point
    #3) Non-match (not identical) = -10 points
    #4) Opening a gap: -20 points
    #5) keeping a gap open: -10 
    
    #reasoning: we may be OK with a mutation, but a missing residue
    #insertion or deleting will be punished much harder.                
    #The options have been chosen to force the best fit locally
    #and highly discourage gaps, as they do not make sense in 
    #this structral space. 
    pdb_sequence = ''.join(AA_pdb)
    alignments = pairwise2.align.localms(uniprot_sequence, pdb_sequence, 1, -10, -20, -10)
    
    if alignments != []: # and alignments[0][2] >= 10:
        uniprot_aligned = alignments[0][0]
        pdb_aligned = alignments[0][1]
        
    else:
        uniprot_aligned = []
        pdb_aligned = []
    
    return uniprot_aligned, pdb_aligned

def numerical_alignment(aligned, positions):
    print("FUNCTION: numerical_alignment(aligned, positions)")
    pos_list = np.array([])             
    for i in range(len(aligned)): 
        if list(aligned)[i] == '-': 
            pos_list=np.append(pos_list,[0], axis=0)
        elif list(aligned)[i] != '-':
            pos_list=np.append(pos_list,positions, axis=0)
            break
    if len(aligned) > len(pos_list):
        N = len(aligned) - len(pos_list)
        pos_list = np.pad(pos_list, (0, N), 'constant') 
    pos_list = pos_list.astype(int)
    return pos_list

def get_uniprot_sequence(uniprot_id, isoform):
    print("FUNCTION: get_uniprot_sequence(uniprot_id, isoform)")
    uniprot_Url="https://rest.uniprot.org/uniprotkb/"
    
    #Alignment to correct isoform:
    if isoform == 1:
    
        fasta_url=uniprot_Url+uniprot_id+".fasta"
        response = requests.post(fasta_url)
        sequence_data=''.join(response.text)
        Seq=StringIO(sequence_data)
        pSeq=list(SeqIO.parse(Seq,'fasta'))
        uniprot_sequence = str(pSeq[0].seq)
        uniprot_numbering = list(range(1,len(uniprot_sequence)+1,1)) 
        #gaining a list of aminoacids and a list of numberical values 
        #indicating the number of each position. 
    
    else:
    
        fasta_url=uniprot_Url+uniprot_id+"-"+str(isoform)+".fasta"
        response = requests.post(fasta_url)
        sequence_data=''.join(response.text)
        Seq=StringIO(sequence_data)
        pSeq=list(SeqIO.parse(Seq,'fasta'))
        uniprot_sequence = str(pSeq[0].seq)
        uniprot_numbering = list(range(1,len(uniprot_sequence)+1,1)) 
    
    return uniprot_sequence, uniprot_numbering

def download_pdb(pdb_id):
    print("FUNCTION: download_pdb(pdb_id)")
    
    pdb = PDBList()
    pdb.retrieve_pdb_file(pdb_id, file_format="pdb", pdir='structure')
    pdbfile = (f"structure/pdb{pdb_id.lower()}.ent")
    pdb_parser = PDB.PDBParser()
    
    try:
        structure = pdb_parser.get_structure(" ", pdbfile)
        model = structure[0]
        return model, structure
    except IOError:
        print("PDBfile cannot be downloaded")
        return np.array([0, 0])


def get_AA_pos(chain_str, model):
    print("FUNCTION: get_AA_pos(chain_str, model)")
    chain = model[chain_str]
    pos_pdb = []
    AA_pdb = []
    n = 0
    for i, residue in enumerate(chain.get_residues()):
        AA_pdb.append(seq1(residue.resname)) 
        if residue.id[2] == ' ':
            pos_pdb.append(residue.id[1]+n)
        else:
            n = n+1
            pos_pdb.append(residue.id[1]+n)        
        #pos_pdb.append(residue.id[1])
    
    AA_pdb = ['-' if item == '' else item for item in AA_pdb]
    if len(list(set(AA_pdb))) != 1:
        
        while AA_pdb[0] == "X":
            AA_pdb = AA_pdb[1:]
            pos_pdb = pos_pdb[1:]
        
        AA_pdb.reverse()
        pos_pdb.reverse()
        
        while AA_pdb[0] == "X":
            AA_pdb = AA_pdb[1:]
            pos_pdb = pos_pdb[1:]
            
        AA_pdb.reverse()
        pos_pdb.reverse()
        
        AA_pdb = ['-' if item == 'X' else item for item in AA_pdb] 
        
        if '-' in AA_pdb and len(AA_pdb) < 5:
            #arbitrary number, if that short, unlikely 
            #to be a true fragment. 
            AA_pdb = []
            pos_pdb = []
            return AA_pdb, pos_pdb 
        
        d = pd.DataFrame({'pos':pos_pdb, 'AA': AA_pdb})
        d = d.drop_duplicates(keep="first")
        AA_pdb = list(d.AA)
        pos_pdb = list(d.pos)
    
    else: 
        AA_pdb = []
        pos_pdb = []
        return AA_pdb, pos_pdb 

    if sorted(pos_pdb) == list(range(min(pos_pdb), max(pos_pdb)+1)):
        return AA_pdb, pos_pdb 
    

    elif len(set(pos_pdb)) != len(pos_pdb): #numbers are used multiple times
        #in a situation where this is the case, such as 1KMC the model
        #is not a good representative
        print("ALIGNMENT SKIPED: PDBfile contains multiple assignments of amino acids to the same residue number")
        AA_pdb = []
        pos_pdb = []
        return AA_pdb, pos_pdb 
        
    else:
        for i in range(len(pos_pdb)-1):
            if pos_pdb[i]+1 != pos_pdb[i+1]:
                pos_pdb.insert(i+1, pos_pdb[i]+1)
                AA_pdb.insert(i+1, "-")
        return AA_pdb, pos_pdb 
    
def remove_missing_residues(structure, pos_pdb, AA_pdb, chain_str):
    print("FUNCTION: remove_missing_residues(structure, pos_pdb, AA_pdb, chain_str)")
    missing_AA = []
    missing_pos = []
    
    #find reported missing residues
    for i in enumerate(structure.header['missing_residues']):
        if chain_str in structure.header['missing_residues'][i[0]]['chain']:
            missing_AA.append(seq1(structure.header['missing_residues'][i[0]]['res_name']))
            missing_pos.append(structure.header['missing_residues'][i[0]]['ssseq'])
    
    #check if these are part of a tag
    t = ("").join(missing_AA)
    if "HHH" in t:
        warning = "The structure likely contains an expression tag"
    else:
        warning = ""
    
    #handle the reported missing residues
    if missing_AA != []:
        for position in missing_pos:
            if position in pos_pdb:
                AA_pdb[pos_pdb.index(position)] = "-"
    
    #handle the missing residues annotated "X"
    for AA in AA_pdb:
        if AA == "X":
            AA_pdb[AA_pdb.index(AA)] = "-"
    
    return AA_pdb, warning
    
def get_mutations(mut_pos, df):
    print("FUNCTION: get_mutations(mut_pos, df)")
    muts = []
    for mutational_positon in list(set(mut_pos)): 
        if mutational_positon in list(df.uniprot_pos): 
            new_df = df[df.uniprot_pos == mutational_positon]
            mutation = list(new_df.uniprot_seq)[0]+str(list(new_df.uniprot_pos)[0])+list(new_df.pdb_seq)[0]
            muts.append(str(mutation))
        else:
            muts.append(f"Mutation on position {mutational_positon} not in range")    
    return muts

def get_all_discrepancies(df):
    print("FUNCTION: get_all_discrepancies(df)")
    #creating empty lists
    mutations_in_all = []
    mut_hotspot = []
    removal_values = np.array([])
    warnings = []
    
    #find all the discrepancies between the uniprot and pdb sequence
    for item in df.index:
        if df["uniprot_seq"][item] != df["pdb_seq"][item]: 
            mut_hotspot.append(list(df.uniprot_pos)[item])
    
    #identify start and end values
    seq_start = list(df.uniprot_pos)[0]
    seq_end = list(df.uniprot_pos)[-1]

    #Coversion to array
    mut_hotspot = np.array(mut_hotspot)
    
    #if the PDB covers the very begining of the canonical sequence
    #any additions to the n-terminal is mutations at position "0". 
    stepsize = 0
    n_ter_0 = np.split(mut_hotspot, np.where(np.diff(mut_hotspot) != stepsize)[0]+1)
    if 0 in n_ter_0[0]:
        l = len(n_ter_0[0])
        removal_values = np.insert(removal_values, 0, 0)
        #removal_values.append(0)
        warnings.append(f"attachment at N-terminal with length {l} have been removed from coverage")
    
    #altenatively, the PDB may cover a different part of the canonical 
    #sequence, and any addition will be numbered consequtively.
    stepsize = 1
    hotspot = np.split(mut_hotspot, np.where(np.diff(mut_hotspot) != stepsize)[0]+1)
    for i in hotspot:
        if len(i) > 2:
            if seq_start in i:
                l = len(i)
                removal_values = np.insert(removal_values, 0, i)
                warnings.append(f"attachment at N-terminal with length {l} have been removed from coverage")
            if seq_end in i:
                l = len(i)
                removal_values = np.insert(removal_values, 0, i)
                warnings.append(f"attachment at C-terminal with length {l} have been removed from coverage")
    
    removal_values = removal_values.flatten() 
    df = df[~df['uniprot_pos'].isin(removal_values)]
    
    df = df.reset_index(drop=True)
    
    for item in df.index:
        if df["uniprot_seq"][item] != df["pdb_seq"][item]: 
            mutations_in_all.append(f"{list(df.uniprot_seq)[item]}{str(list(df.uniprot_pos)[item])}{list(df.pdb_seq)[item]}")

    return df, mutations_in_all, warnings

def get_coverage(df):
    print("FUNCTION: get_coverage(df)")
    ranges_covered = list(to_ranges(list(df.uniprot_pos)))
    ranges_covered = str(ranges_covered)
    ranges_covered = ranges_covered.replace("), (", ");(" )
    return ranges_covered
        
def align_uniprot_pdb(pdb_id, uniprot_sequence, uniprot_numbering, mut_pos, path, complex_protein_details, complex_nucleotide_details, self_chains, uniprot_id):
    print("===========================================")
    print(pdb_id)
    print("===========================================")
    
    print("FUNCTION: align_uniprot_pdb(pdb_id, uniprot_sequence, uniprot_numbering, mut_pos, path, complex_protein_details, complex_nucleotide_details, self_chains, uniprot_id)")
    """
    ...

    Parameters
    ----------
    pdb_id : A particular string containg the foru letter code to a pdb id
    uniprot_id : A string containing the uniprot id
    isoform : an interger 
    mut_pos : an array of positions the user wish to cover with the structure.
    path : directory string.

    Returns
    -------
    output_array: An np.array containing: 
        1. chains_string e.g. 'A';'B', description of each related chain
        2. coverage_string, e.g. [(1,123);(4,74)] area of alignment per chain 
        3. mutational_column_string e.g. [E17K;T74E],[E17E;T74T]
        4. mutation_list_string, eg., [P78K];[], these are often mutations
            introduced in the experiment to keep the protein stable or to 
            investigate a particular phenomenon.

    """
    
    #Create a structure directory. 
    if os.path.exists("structure") == False:
        os.mkdir("structure")
    
    # Empty lists for popultion by function
    muts = []
    coverage = []
    mutational_column = []
    mutation_list = []
    chains = []
    warning_column = []
    
    #download model
    model, structure = download_pdb(pdb_id)
    if model == 0: 
        return ['']
    
    #find all chains in the structure   
    for chain_str in self_chains:  
        print(f"CHAIN: {chain_str}")
        chain_warning = [] 
        AA_pdb, pos_pdb = get_AA_pos(chain_str, model)
        if AA_pdb == []:
            os.chdir(path)
            output_array = np.array(['', '', '', '', ''], dtype=object)
            return output_array

        if structure.header['has_missing_residues'] == True:
            AA_pdb, warning = remove_missing_residues(structure, pos_pdb, AA_pdb, chain_str)
            chain_warning.append(warning)

        uniprot_aligned, pdb_aligned = alignment(uniprot_sequence, AA_pdb)    
                
        if uniprot_aligned != []:
            chains.append(chain_str)
            uniprot_pos_list = numerical_alignment(uniprot_aligned, uniprot_numbering)
            pdb_pos_list = numerical_alignment(pdb_aligned, pos_pdb)
    
            df = pd.DataFrame(data={"uniprot_seq": list(uniprot_aligned), 
                                    "uniprot_pos": uniprot_pos_list, 
                                    "pdb_seq": list(pdb_aligned), 
                                    "pdb_pos": pdb_pos_list})       
            
            df = df[df.pdb_seq!="-"]
        
            if type(mut_pos) == list:
                muts = get_mutations(mut_pos, df)
                mutational_column.append(muts)
            #capture all mutations in PDBfile compared to the specified 
            #protein isoform.
            df = df.reset_index(drop=True)
        
            df, mutations_in_all, warnings = get_all_discrepancies(df)
            chain_warning.append(warnings)
            chain_warning = ",".join([str(elem) for elem in chain_warning])
            
            replacements = [("[", ""), ("]", ""), ("'", "")] 
            chain_warning = [chain_warning := chain_warning.replace(a, b) for a, b in replacements]
            chain_warning = chain_warning[-1]
            
            warning_column.append(chain_warning)
                        
            #multiple warnings in one chain
            if mutations_in_all == []:
                mutation_list.append("NA")
            else:
                mutation_list.append(mutations_in_all)

            #capture the area the PDB covers accourding to the alignment. 
            ranges_covered = get_coverage(df)
            coverage.append(ranges_covered)
            
    chains_string = ';'.join([str(elem) for elem in chains])
    coverage_string = ';'.join([str(elem) for elem in coverage])
    mutational_column_string = ';'.join([str(elem) for elem in mutational_column])    
    mutation_list_string = ';'.join([str(elem) for elem in mutation_list])
    warning_column_string = ";".join([str(elem) for elem in warning_column])
    if warning_column_string == ",":
        warning_column_string = "NA"
    elif warning_column_string.startswith(","):
        warning_column_string = warning_column_string[1:]
        
    output_array = np.array([chains_string, coverage_string, mutational_column_string, mutation_list_string, warning_column_string], dtype=object)
    os.chdir(path)
    return output_array


def align_alphafold(alphafold_id, mutation_positions):
    print("FUNCTION: align_alphafold(alphafold_id, mutation_positions)")
    """
    This function takes an alphafold ID and the mutational positions. 
    The aim is to find the high quality areas of the protein, and set these in 
    relation to the mutations. 

    Parameters
    ----------
    alphafold_id : String of the ID
    mutation_positions : List of mutations

    Returns
    -------
    coverage : [(x, y)] per chain high quality areas (pDDLT > 70)
    AA_in_PDB : If the high quality portions of the AF structure covers 
    mutations. 

    """
    
    url = (f"'https://alphafold.ebi.ac.uk/files/{alphafold_id}.pdb'")
    os.system(f"wget {url}")
    
    ppdb = PandasPdb().read_pdb(f"{alphafold_id}.pdb")
    ATOMS = ppdb.df['ATOM']
    ATOMS = ATOMS[ATOMS.atom_name == "CA"]
    confidence_list = list(ATOMS['b_factor'])
    positions = np.array(range(1,len(ATOMS)+1))
    sequence = list(seq1(''.join(list(ATOMS.residue_name))))

    confidence_categories = []
    for i in range(len(confidence_list)):
        if confidence_list[i] > 70:
            confidence_categories.append("high")
        else:
            confidence_categories.append("low")
            
    #create an intermediate df containing the quality estimates
    df = pd.DataFrame({'position':positions,'sequence':sequence,'PDDLT':confidence_list,'category':confidence_categories})    
    confident_seq = np.array(df[df.category == "high"].position)
        
    if len(confident_seq) > 0:
#create coverage string (PDBminer output style)
        f = []
        f.append(confident_seq[0])
        for i in range(len(confident_seq)-1):
            if confident_seq[i]+1 != confident_seq[i+1]:
                f.append(confident_seq[i])
                f.append(confident_seq[i+1])
        f.append(confident_seq[-1])
    
        f = np.array(f)
        coverage = []
        for i in range(len(f[::2])):
            p = f[::2][i],f[1::2][i] 
            coverage.append(p)
        
        coverage = str(coverage)
        coverage = coverage.replace("), (", ");(" )
    
        AA_in_PDB = []
    
        for i in range(len(mutation_positions)):
            if mutation_positions[i] == "NA":
                mutation = "NA"
            else:
                if df.category[df.position == mutation_positions[i]].values == "high":
                    mutation = f"{df.sequence[df.position == mutation_positions[i]].values[0]}{mutation_positions[i]}{df.sequence[df.position == mutation_positions[i]].values[0]}"
                else:
                    mutation = 'Mutation not in range'
            
            AA_in_PDB.append(mutation)
    
        AA_in_PDB = ",".join(AA_in_PDB)

    else: 
        coverage = "NA"
        AA_in_PDB = "NA"
    #output coverage string
    return coverage, AA_in_PDB

def align(combined_structure, path):
    print("FUNCTION: align(combined_structure, path)")
    """
    This functions takes the pandas dataframe containing all the structures, 
    their metadata and information regarding mutations of interest, import 
    the relevant fastafiles and conduct alignment, which captures information
    regarding the structure in terms of mutations. All is outputted as 
    additional columns in the input file.

    Parameters
    ----------
    combined_structure : Pandas dataframe created in step 3.
    path : string, directory of interest.

    Returns
    -------
    combined_structure : Updated input. 
    """
    
    combined_structure["chains"] = " "
    combined_structure["coverage"] = " "
    combined_structure["AA_in_PDB"] = " "
    combined_structure["mutations_in_pdb"] = " "
    combined_structure["warnings"] = " "
    
    uniprot_sequence, uniprot_numbering = get_uniprot_sequence(combined_structure.uniprot_id[0], int(combined_structure['uniprot_isoform'][0]))     

    for i in range(len(combined_structure)):
        
        if type(combined_structure['mutations'][i]) != str:
            combined_structure['mutation_positions'] = "NA"
        else:
            combined_structure['mutation_positions'] = combined_structure['mutations'].str.split(';').apply(lambda x: [int(y[1:-1]) for y in x])
        
        if combined_structure['structure_id'][i].startswith("AF"):
            alignment_info = align_alphafold(combined_structure['structure_id'][i], combined_structure['mutation_positions'][i])
            
            combined_structure.at[i, 'chains'] = "A"  
            combined_structure.at[i, 'coverage'] = alignment_info[0] 
            combined_structure.at[i, 'AA_in_PDB'] = alignment_info[1] 
            combined_structure.at[i, 'mutations_in_pdb'] = "NA"
            combined_structure.at[i, 'warnings'] = "NA"
            
        else:    
            #uniprot_sequence, uniprot_numbering = get_uniprot_sequence(combined_structure.uniprot_id[i], int(combined_structure['uniprot_isoform'][i]))     
            alignment_info = align_uniprot_pdb(combined_structure.structure_id[i],
                                           uniprot_sequence, 
                                           uniprot_numbering,
                                           combined_structure['mutation_positions'][i],
                                           path,
                                           combined_structure.complex_protein_details[i], 
                                           combined_structure.complex_nucleotide_details[i],
                                           combined_structure.self_chains[i],
                                           combined_structure.uniprot_id[i])

            if alignment_info[0] != '':
                combined_structure.at[i, 'chains'] = alignment_info[0]  
                combined_structure.at[i, 'coverage'] = alignment_info[1] 
                combined_structure.at[i, 'AA_in_PDB'] = alignment_info[2] 
                combined_structure.at[i, 'mutations_in_pdb'] = alignment_info[3]
                combined_structure.at[i, 'warnings'] = alignment_info[4]
        
            #drop missing values. 
            else:
                combined_structure = combined_structure.drop([i])
    
    combined_structure = combined_structure.reset_index(drop=True)  
                        
    return combined_structure


#============================================================================#
# 5)  The PDB files are then analyzed in terms of other present proteins, 
#     indicating a complex, ligands and other molecules present. 
#============================================================================#
# This step consist of one function. 
#
#   get_complex_information(pdb_id)
#   collect_complex_info(structural_df)
#
#   The first function is called through collect_complex_info.
#   The aim is to take the structural dataframe as input and output
#   a structural dataframe including complex and ligand columns. 
#

def get_complex_information(pdb_id, uniprot):
    print(f"FUNCTION: get_complex_information(pdb_id, uniprot), {pdb_id}, {uniprot}")
    """
    This function takes a PDB id and analyzes its content to estabilish if 
    there is any other elements within the file such as a ligand. 
    

    Parameters
    ----------
    pdb_id : Four letter code, string. 

    Returns
    -------
    output_array: A np.array contoning of 
                1) protein_complex_list: binary  
                2) protein_info; description of complex if any
                3) self_chain; a double check list of chains annotated as self
                4) nucleotide_complex_list: binary 
                5) nuleotide_info: description of complex if any 
                6) ligand_complex_list: binart 
                7) ligand_info: description of complex if any. Include metal.

    """    
    #finding protein complexes and their related uniprot_ids 
    #this step also serves as a quality control of uniprot id's and chains.
    
    try: 
        response = requests.get(f"https://www.ebi.ac.uk/pdbe/api/mappings/uniprot_segments/{pdb_id}")
    except ConnectionError as e:
        with open("log.txt", "a") as textfile:
            textfile.write(f"EXITING: PDBe database API controlled and rejected for {pdb_id}, connection error. \n")
        exit(1) 
    
    if response.status_code == 200:
        response_text = json.loads(response.text)
        protein_segment_dictionary = response_text[pdb_id.lower()]
        
        self_chain = []
    
        if len(protein_segment_dictionary['UniProt']) <= 1:
            protein_complex_list = "NA"
            protein_info = "NA"    
            
            #check that uniprot found the correct PDB:
            if list(protein_segment_dictionary['UniProt'].keys())[0] != uniprot:
                output_array = np.array(['NA', 'NA', 'NA', 'NA', 
                                         'NA', 'NA', 'NA'], dtype=object)
                return output_array
            
            else:               
                #allow isoforms
                for i in next(v for k,v in protein_segment_dictionary['UniProt'].items() if uniprot in k)['mappings']:
                    self_chain.append(i['chain_id'])
                self_chain = list(set(self_chain))
                
        else: 
            if uniprot not in list(protein_segment_dictionary['UniProt'].keys()):
                output_array = np.array(['NA', 'NA', 'NA', 'NA', 
                                         'NA', 'NA', 'NA'], dtype=object)
                return output_array

            else:            
                #allow isoforms
                for i in next(v for k,v in protein_segment_dictionary['UniProt'].items() if uniprot in k)['mappings']:
                    self_chain.append(i['chain_id'])
                self_chain = list(set(self_chain))
                
                info = []
                fusion_test = []
                for i in protein_segment_dictionary['UniProt']:
                    prot_info = f"{protein_segment_dictionary['UniProt'][i]['identifier']}, {i}, chain_{protein_segment_dictionary['UniProt'][i]['mappings'][0]['chain_id']}"
                    info.append(prot_info)
                    
                for item in enumerate(info):
                    fusion_test.append(item[1][-1])
                    if uniprot in item[1]:
                        value = item[0]
                
                if len(set(fusion_test)) == 1:
                    protein_complex_list = 'fusion product'
                elif len(fusion_test) > len(set(fusion_test)):
                    if fusion_test.count(fusion_test[value]) > 1:
                        protein_complex_list = 'fusion product in protein complex'
                    else:
                        protein_complex_list = 'protein complex with fusion product'
                else:
                    protein_complex_list = 'protein complex'
            
                info = ';'.join(info)
                protein_info = [info] 

    else:
        protein_complex_list = "NA"
        protein_info = "NA"
    
    #finding complexes with other ligands by identifying other molecules
    try: 
        response = requests.get(f"https://www.ebi.ac.uk/pdbe/api/pdb/entry/molecules/{pdb_id}")
    except ConnectionError as e:
        with open("log.txt", "a") as textfile:
            textfile.write(f"EXITING: PDBe database API for molecules controlled and rejected for {pdb_id}, connection error. \n")
        exit(1) 

    response_text = json.loads(response.text)
    molecule_dictionary = response_text[pdb_id.lower()]

    nucleotide_info = []
    ligand_info = []
    
    for i in range(len(molecule_dictionary)):
        
        if "nucleotide" in molecule_dictionary[i]['molecule_type']:
            n1 = molecule_dictionary[i]['molecule_name'][0]
            n2 = molecule_dictionary[i]['in_chains']
            n2 = ",".join(n2)
            n = f"{n1}, chain {n2}"
            #n = f"[{molecule_dictionary[i]['molecule_type']}, {molecule_dictionary[i]['in_chains']}]"
            nucleotide_info.append(n)
        
        elif molecule_dictionary[i]['molecule_type'] != 'polypeptide(L)':
            if molecule_dictionary[i]['molecule_type'] != 'water': 
                l1 = molecule_dictionary[i]['molecule_name'][0]
                l2 = molecule_dictionary[i]['in_chains']
                l2 = ",".join(l2)
                l = f"{l1}, chain {l2}"
                #l = f"[{molecule_dictionary[i]['molecule_name'][0]}, {molecule_dictionary[i]['in_chains']}]"
                ligand_info.append(l)
   
    if len(nucleotide_info) > 0:
        nucleotide_complex_list = 'nucleotide complex'
        if len(nucleotide_info) > 1: 
            nucleotide_info = ';'.join(nucleotide_info)
    
    else: 
        nucleotide_complex_list = "NA"
        nucleotide_info = "NA"
           
    if len(ligand_info) > 0:
        ligand_complex_list = "Other ligands"
        if len(ligand_info) > 1: 
            ligand_info = ';'.join(ligand_info)
    
    else: 
        ligand_complex_list = "NA"
        ligand_info = "NA"
            
    output_array = np.array([protein_complex_list, protein_info, self_chain, nucleotide_complex_list, 
                             nucleotide_info, ligand_complex_list, ligand_info], dtype=object)
    
    return output_array

def collect_complex_info(structural_df):
    print("FUNCTION: collect_complex_info(structural_df)")
    """
    A function that parses all pdbids though the get_complex_information
    function and capture and merge with the input file. 

    Parameters
    ----------
    structural_df: The pandas dataframe containing the original input file,
                   PDBs and subsequent additional columns. 
    
    Returns
    -------
    df_combined: A format of the structural_df including complex information. 

    """
    
    uniprot_id = structural_df['uniprot_id'][0]
    
    df = pd.DataFrame(columns=['structure_id','complex_protein',
                           'complex_protein_details', 'self_chains', 'complex_nucleotide',
                           'complex_nucleotide_details','complex_ligand', 
                           'complex_ligand_details'])

    for pdb in set(structural_df['structure_id']):
        
        if pdb.startswith("AF-"):
            list_of_values = [pdb,'NA',
                              'NA',['A'],
                              'NA','NA',
                              'NA','NA']
            
        else:
            complex_info = get_complex_information(pdb, uniprot_id)
    
            list_of_values = [pdb, complex_info[0], 
                              complex_info[1], complex_info[2], 
                              complex_info[3], complex_info[4], 
                              complex_info[5], complex_info[6]]
            
        if list_of_values[3] != 'NA':
        
            df.loc[pdb] = np.array(list_of_values, dtype="object") 
    
    df_combined = pd.merge(structural_df, df, how='inner', on = 'structure_id')
    
    return df_combined


#============================================================================#
# 6)  All these informations is reported in all_{uniprot_id}_structural_df.csv
#     This is done in PDBminer_run

#============================================================================#


#============================================================================#
# 7)  A cleanup of the path removing structures and if structures.
#     This is done in PDBminer_run
#============================================================================#        


#============================================================================#
# 8)  The structural_df if cleaned only keeping the PDB files that at 
#     least cover one of the specifed mutations. This is reported as
#     clean_{uniprot_id}_structural_df.csv. If there is no structures 
#     that cover the mutations, a txt file is reported indicating 
#     that an alphafold structure may be the next path. 
#============================================================================#        
# This step consist of two functions.
# 
#   cleanup_all(structural_df)
#   filter_all(structural_df)
#
#   The aim is to take the structural dataframe as input and output
#   he structural dataframe with simple ammendments. This step sould
#   become obsolete in time, when prior functions are improved. 

def cleanup_all(structural_df):
    print("FUNCTION: cleanup_all(structural_df)")

    structural_df = structural_df.drop(columns=['AA_in_PDB', 'mutation_positions', 'self_chains'])
    
    for i in range(len(structural_df.mutations_in_pdb)):
        if set(structural_df.mutations_in_pdb[i].split(";")) == {'NA'}:
            structural_df.iloc[i, structural_df.columns.get_loc('mutations_in_pdb')] = 'NA'
        
    for i in range(len(structural_df.warnings)):
        if set(structural_df.warnings[i].split(";")) == {'', ','}:
            structural_df.iloc[i, structural_df.columns.get_loc('warnings')] = 'NA'
    
    structural_df.index.name = 'structure_rank'

    return structural_df

def filter_all(structural_df, input_dataframe):
    print("FUNCTION: filter_all(structural_df, input_dataframe)")
    """
    This function cleans up sloppy coding from earlier in the pipeline
    which is needed for further investigation by removing structures that 
    does not satisfy the criteria.

    Parameters
    ----------
    structural_df : The pandas dataframe containing the original input file,
                   PDBs and subsequent additional columns. 

    Returns
    -------
    structural_df : The pandas dataframe containing the original input file,
                   PDBs that cover at least ONE mutation. 

    """
    
    final_dfs = []
    
    #remove sturctures where no mutations are within range    
    replacements = [(";",","), ("[", ""), ("]", ""), ("'", ""), (" M", "M")]

    for i in range(len(structural_df.mutation_positions)):
        chains = structural_df.AA_in_PDB[i]
        chains = [chains := chains.replace(a, b) for a, b in replacements]
        chains = chains[-1]
        while chains[0] == ",":
            chains = chains[1:]

        if "," in chains: 
            chains = chains.split(",")
            t = [x.split()[0] for x in chains]
            if list(set(t)) == ['Mutation']:  
                structural_df = structural_df.drop([i])
        else: 
            if chains == '':
                structural_df = structural_df.drop([i])
            elif chains.split()[0] == 'Mutation':
                structural_df = structural_df.drop([i])
    
    structural_df = structural_df.reset_index(drop=True)  
        
    #Remove structures with only mismatch in alignment
    for i in range(len(structural_df.coverage)):
        if list(set(structural_df.coverage[i].split(";"))) == ['Mismatch in alignment']:
            structural_df = structural_df.drop([i])
    
    structural_df = structural_df.reset_index(drop=True)
    
    for i in range(len(structural_df.mutations_in_pdb)):
        if set(structural_df.mutations_in_pdb[i].split(";")) == {'NA'}:
            structural_df.iloc[i, structural_df.columns.get_loc('mutations_in_pdb')] = 'NA'
        
    for i in range(len(structural_df.warnings)):
        if set(structural_df.warnings[i].split(";")) == {'', ','}:
            structural_df.iloc[i, structural_df.columns.get_loc('warnings')] = 'NA'

    structural_df = structural_df.drop(columns=['mutation_positions'])
    structural_df = structural_df.reset_index(drop=True)
    
    if len(set(input_dataframe.cluster_id)) != 1:
        for cluster in list(input_dataframe.cluster_id):
            cluster_df = structural_df[structural_df.cluster_id == cluster]
            cluster_df = cluster_df.reset_index(drop=True)
            cluster_df.index.name = 'structure_rank'
            final_dfs.append(cluster_df)
    
    else:
        structural_df.index.name = 'structure_rank'
        final_dfs.append(structural_df)

    return final_dfs
