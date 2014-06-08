#!/usr/bin/env python3

import sys
import argparse
import gzip
import bz2
import re
import string
import utils

argparser = argparse.ArgumentParser()
argparser.add_argument("chr", help="Chromosome in the masterVar file")
argparser.add_argument("sample_id", help="Sample ID to put into the VCF file")
argparser.add_argument("out_mask", help="Prefix for mask- and vcf file")
argparser.add_argument("input", help="Complete Genomics masterVarBeta file (uncompressed or compressed with gzip or bzip2)")
argparser.add_argument("--max_pos", type=int, default=0)
argparser.add_argument("--legend_file", help="Impute2 reference panel legend file, can be gzipped or not")
args = argparser.parse_args()

mask_generator = utils.MaskGenerator(args.out_mask, args.chr)
sites_parser = None
if args.legend_file is not None:
    sites_parser = utils.LegendParser(args.legend_file)

print("##fileformat=VCFv4.1")
print('##FORMAT=<ID=GT,Number=1,Type=String,Description="Phased Genotype">')

print("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{}".format(args.sample_id))

input_file = None
if args.input[-3:] == ".gz":
    input_file = gzip.open(args.input, "rt")
elif args.input[-4:] == ".bz2":
    input_file = bz2.open(args.input, "rt")
else:
    input_file = open(args.input, "rt")
    
line_count = 0
chromosome_read = False
for line in input_file:
    if line[0] == '#' or line[0] == '>' or line == "\n":
        continue
    line_count += 1
    if line_count % 100000 == 0:
        sys.stderr.write("processing line {}\n".format(line_count))
      
    fields = line.strip().split()
    
    chrom = fields[2]
    begin = int(fields[3])
    end = int(fields[4])
    
    if chrom != args.chr:
        if chromosome_read:
            break
        else:
            continue
  
    if args.max_pos > 0 and end > args.max_pos:
        break
    chromosome_read = True
    zygosity = fields[5]
    var_type = fields[6]
    
    
    if var_type == "ref" and zygosity == "hom":
        for i in range(begin + 1, end + 1):
            mask_generator.addCalledPosition(i)
            if sites_parser is not None:
                while not sites_parser.end and sites_parser.pos < i:
                    sites_parser.tick()
                if sites_parser.pos == i:
                    print("{chrom}\t{pos}\t.\t{ref_a}\t{alt_a}\t.\tPASS\t.\tGT\t0/0".format(chrom=args.chr, pos=i, 
                                                                                      ref_a=sites_parser.ref_a,
                                                                                      alt_a=sites_parser.alt_a))
  
    if var_type == "snp":
        if zygosity in ["hom", "het-ref", "het-alt"]:
            assert end - begin == 1, "ERROR: found SNP which is longer than 1bp at position {}. This may indicate that you are using a newer version than 2.2 of the Complete Genomics Pipeline, which is not yet supported".format(begin + 1)
                continue
            allele_ref = fields[7]
            if sites_parser is not None:
                while not sites_parser.end and sites_parser.pos < begin + 1:
                    sites_parser.tick()
                if sites_parser.pos == begin + 1:
                    assert allele_ref == sites_parser.ref_a
            allele_1 = fields[8]
            allele_2 = fields[9]
            allele1_qual = fields[14]
            allele2_qual = fields[15]
            if allele1_qual == "VQHIGH" and allele2_qual == "VQHIGH":
                mask_generator.addCalledPosition(begin + 1)
                allele_indices = []
                alt_alleles = []
                if allele_1 != allele_ref:
                    alt_alleles.append(allele_1)
                    allele_indices.append(1)
                if allele_2 == allele_ref:
                    allele_indices.append(0)
                elif allele_2 == allele_1:
                    allele_indices.append(1)
                else:
                    alt_alleles.append(allele_2)
                    allele_indices.append(2)
                print("{chrom}\t{pos}\t.\t{ref_a}\t{alt_a}\t.\tPASS\t.\tGT\t{gen1}/{gen2}".format(chrom=args.chr, 
                       pos=begin+1, ref_a=allele_ref, alt_a=",".join(alt_alleles), gen1=allele_indices[0], gen2=allele_indices[1]))