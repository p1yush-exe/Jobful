insert into canonical_tags (tag_name) values
  -- engineering
  ('frontend'),
  ('backend'),
  ('fullstack'),
  ('mobile'),
  ('embedded-systems'),
  ('systems-programming'),
  ('devops'),
  ('cloud'),
  ('security'),        -- absorbs cybersecurity, infosec, appsec
  ('testing'),
  ('software development'),

  -- ai / data
  ('ai-ml'),           -- absorbs ML, DL, NLP, CV, LLMs
  ('data-science'),    -- absorbs analytics, statistics, modelling
  ('data-engineering'),-- absorbs pipelines, ETL, warehousing
  ('research'),        -- absorbs academic, R&D, applied science
  ('automation'),      -- absorbs RPA, scripting, workflow tools

  -- product / business
  ('product-management'),         -- absorbs PM, product strategy, roadmapping
  ('consulting'),      -- absorbs advisory, solutions architecture
  ('technical-writing'),
  ('agile'),           -- absorbs scrum, kanban, delivery management

  -- design / creative
  ('ui-ux'),           -- absorbs UI, UX, interaction design separately
  ('product-design'),  -- absorbs end-to-end design ownership
  ('graphic-design'),  -- absorbs branding, visual identity, print
  ('motion-design'),   -- absorbs animation, VFX, motion graphics
  ('video-editing'),   -- absorbs post-production, colour grading
  ('content-creation'),-- absorbs social media, blogging, copywriting
  ('photography'),
  ('3d-modelling'),    -- absorbs CAD, sculpting, rendering

  -- emerging / specialised
  ('game-development'),
  ('ar-vr'),           -- absorbs XR, spatial computing, metaverse
  ('robotics'),        -- absorbs ROS, mechatronics, control systems
  ('blockchain'),      -- absorbs web3, smart contracts, defi, crypto
  ('ios'),             -- kept separate — skill set is distinct enough
  ('android'),         -- kept separate — same reason

  -- hardware / science
  ('electronics'),     -- absorbs circuit design, PCB, FPGA
  ('biotech'),         -- absorbs bioinformatics, computational biology
  ('fintech'),         -- absorbs payments, trading systems, regtech

  -- operations
  ('sales-growth'),    -- absorbs growth hacking, biz dev, GTM
  ('operations'),      -- absorbs ops, supply chain, logistics
  ('hr-people'),       -- absorbs recruiting, people ops, L&D
  ('legal-compliance') -- absorbs regulatory, policy, risk
on conflict (tag_name) do nothing;