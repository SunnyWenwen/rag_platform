'use strict';

const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const repo = path.join(__dirname,'..');
const readFixture = name => JSON.parse(fs.readFileSync(path.join(repo,'examples',name),'utf8'));
const html = fs.readFileSync(path.join(repo,'01_ui_prototype.html'),'utf8');
const jsonScripts = Object.fromEntries([...html.matchAll(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g)]
  .map(([,id,textContent]) => [id,{textContent}]));
const [,script] = html.match(/<script>\s*([\s\S]*?)<\/script>/);
const boot = script.indexOf('\nif (!stored) {');
assert.ok(boot > 0,'Prototype startup boundary');
const runtime = vm.createContext({
  crypto:webcrypto,
  structuredClone,
  document:{getElementById:id => jsonScripts[id] ?? {addEventListener() {}},addEventListener() {}},
  localStorage:{getItem:() => null},
  window:{addEventListener() {}}
});
// Load the prototype's actual derivation and validation functions without mounting the UI.
vm.runInContext(script.slice(0,boot),runtime,{filename:'01_ui_prototype.html'});

function verifyDescriptorDerivation(runtime) {
  const shared = readFixture('system_config/descriptor_derivation.fixture.json');
  const catalog = readFixture('system_config/' + shared.catalog_file);
  for (const scenario of shared.cases) {
    const draftConfig = structuredClone(shared.draft);
    for (const [pipeline, modules] of Object.entries(scenario.parameter_overrides ?? {})) {
      for (const [module, values] of Object.entries(modules)) {
        Object.assign(draftConfig.pipelines[pipeline][module].parameters, values);
      }
    }
    const evaluate = ({draftConfig,catalog}) => {
      const oldDescriptors = [...componentCatalog];
      const oldResources = {...resources};
      componentCatalog.splice(0,componentCatalog.length,...catalog.descriptors);
      Object.assign(resources,catalog.resources);
      try {
        const data = derive(draftConfig);
        const vectorBindings = Object.fromEntries(indexVectorNames(draftConfig)
          .filter(name => Object.hasOwn(data.vectorBindings,name)).map(name => [name,data.vectorBindings[name]]));
        const effective = {
          import:[data.input,{}], parsing:[data.parsed,{}], chunking:[data.chunkFields,{}],
          embedding:[data.fields,data.vectorBindings], indexing:[data.indexed,vectorBindings],
          ...Object.fromEntries(lanes.inference.map(module => [module,[data.indexed,data.vectorBindings]]))
        };
        const nodes = Object.fromEntries(Object.entries(effective).map(([module,[fields,vectors]]) => {
          const desc = descriptor(module,draftConfig);
          const options = Object.fromEntries(Object.keys(desc.option_sources ?? {}).map(path =>
            [path,optionValues(draftConfig,module,path).sort()]));
          const structdata = Object.fromEntries(Object.entries(fields).map(([name,field]) =>
            [name,{searchable:false,filterable:false,...field}]));
          return [module,{io:desc.io,effective_schema:{structdata,vectors},options}];
        }));
        // The Prototype's W1 publish validation uses the first mapping as flat parameters.
        const embedding = params(draftConfig,'embedding');
        Object.assign(embedding,embeddingMappings(embedding)[0]);
        const issues = configIssues(draftConfig).map(({module,path}) =>
          ({code:'CONFIG_VALIDATION_FAILED',module,path}));
        return {nodes,errors:issues};
      } finally {
        componentCatalog.splice(0,componentCatalog.length,...oldDescriptors);
        Object.assign(resources,oldResources);
      }
    };
    runtime.fixtureInput = {draftConfig,catalog};
    const actual = JSON.parse(vm.runInContext('JSON.stringify((' + evaluate + ')(fixtureInput))',runtime));
    const nodes = Object.fromEntries(Object.entries(shared.nodes).map(([name,node]) =>
      [name,{...node,effective_schema:shared.effective_schemas[node.effective_schema]}]));
    assert.deepEqual(actual,{nodes,errors:scenario.errors},scenario.name);
  }
}

verifyDescriptorDerivation(runtime);
console.log('PASS: Prototype effective schemas, options and errors match the shared Descriptor fixture');

const identity = JSON.parse(fs.readFileSync(path.join(repo,'schemas/runtime_identity.schema.json'),'utf8'));
const uuidV4 = new RegExp(identity.$defs.uuid_v4.pattern);
const {system, migrated, indexName} = vm.runInContext(`
  localStorage.getItem = () => JSON.stringify({systems:[{
    id:'product-faq', active:{}, indexEpoch:2,
    deployment:{loaded:{ingestion:{index_generation:'index-2'},inference:{index_generation:'index-1'}}}
  }]});
  const migrated = load().systems[0];
  ({system:makeSystem('New system',0), migrated, indexName:managedIndexName(migrated)});
`,runtime);
assert.match(system.id,uuidV4);
assert.match(migrated.id,uuidV4);
assert.match(migrated.indexGeneration,uuidV4);
assert.equal(indexName,`rag-builder-${migrated.id}-${migrated.indexGeneration}`);
assert.equal(migrated.deployment.loaded.ingestion.index_generation,migrated.indexGeneration);
assert.notEqual(migrated.deployment.loaded.inference.index_generation,migrated.indexGeneration);
console.log('PASS: Prototype generates UUIDs and preserves readiness when loading older mock state');

const settings = JSON.parse(vm.runInContext(`
  const dev = {secret:{TOKEN:'fixture-secret'},variable:{CHUNK_MAX_TOKENS:'720'}};
  let savedSettings;
  localStorage.setItem = (_,data) => { savedSettings = JSON.parse(data).systems[0].draft; };
  model.systems = [{draft:dev}];
  persist();
  JSON.stringify({
    variableTable:settingTable(dev,'variable'),
    secretTable:settingTable(dev,'secret'),
    saved:savedSettings,
    exported:deploymentConfig(dev)
  });
`,runtime));
assert.match(settings.variableTable,/type="text".*data-setting-value="CHUNK_MAX_TOKENS"/);
assert.match(settings.secretTable,/type="password".*data-setting-value="TOKEN"/);
assert.deepEqual(settings.saved,{secret:{TOKEN:null},variable:{CHUNK_MAX_TOKENS:'720'}});
assert.deepEqual(settings.exported,{secret:{TOKEN:null},variable:{CHUNK_MAX_TOKENS:null}});
console.log('PASS: Prototype renders, saves and exports Variable separately from Secret');
