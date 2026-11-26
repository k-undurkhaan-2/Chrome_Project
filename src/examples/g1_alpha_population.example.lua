-- Public artificial fixture, identical to g1_alpha_population.example.json.
-- Numeric identities/words are table data, never process addresses or reads.
return {
  options={population_mode='full', target_value_pattern=0x42C80000, target_value_float=100.0},
  records={
    {addr=0x100128, mapped=true, protect=4, memory={
      [0x100108]=0x10011200, [0x100118]=0x10013800, [0x100120]=0x10042100,
      [0x100128]=0x42C80000, [0x100158]=0x10060000,
      [0x100168]=0x10025600, [0x100170]=0x10028400, [0x100178]=0x10086300,
    }},
    {addr=0x100328, mapped=true, protect=4, memory={
      [0x100308]=0, [0x100318]=0, [0x100320]=0, [0x100328]=0x42C80000,
      [0x100358]=0, [0x100368]=0, [0x100370]=0, [0x100378]=0,
    }},
    {addr=0x100528, mapped=true, protect=4, memory={
      [0x100508]=0, [0x100518]=0, [0x100520]=0, [0x100528]=0x42C80000,
      [0x100558]=0, [0x100568]=0, [0x100570]=0, [0x100578]=0,
    }},
  },
}
