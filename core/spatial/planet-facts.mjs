export const PLANET_FACTS={
 mercury:{name:'Mercúrio',type:'Planeta rochoso',diameter:'4.879 km',year:'88 dias terrestres',atmosphere:'Exosfera muito tênue',fact:'Apesar de ser o mais próximo do Sol, não é o planeta mais quente.',source:'https://science.nasa.gov/mercury/facts/'},
 venus:{name:'Vênus',type:'Planeta rochoso',diameter:'12.104 km',year:'225 dias terrestres',atmosphere:'Densa, rica em dióxido de carbono',fact:'Sua rotação é retrógrada: gira no sentido oposto ao da Terra.',source:'https://science.nasa.gov/venus/venus-facts/'},
 earth:{name:'Terra',type:'Planeta rochoso',diameter:'12.756 km · equatorial',year:'365,25 dias',atmosphere:'Nitrogênio e oxigênio',fact:'É o único mundo onde a existência de vida foi confirmada.',source:'https://science.nasa.gov/earth/facts/'},
 mars:{name:'Marte',type:'Planeta rochoso',diameter:'6.792 km · equatorial',year:'687 dias terrestres',atmosphere:'Tênue, rica em dióxido de carbono',fact:'Abriga o Monte Olimpo, um enorme vulcão do sistema solar.',source:'https://science.nasa.gov/mars/facts/'},
 jupiter:{name:'Júpiter',type:'Gigante gasoso',diameter:'142.984 km · equatorial',year:'11,86 anos terrestres',atmosphere:'Hidrogênio e hélio',fact:'A Grande Mancha Vermelha é uma tempestade gigantesca.',source:'https://science.nasa.gov/jupiter/jupiter-facts/'},
 saturn:{name:'Saturno',type:'Gigante gasoso',diameter:'120.536 km · equatorial',year:'29,45 anos terrestres',atmosphere:'Hidrogênio e hélio',fact:'Seus anéis são compostos principalmente de partículas de gelo.',source:'https://science.nasa.gov/saturn/facts/'},
 uranus:{name:'Urano',type:'Gigante de gelo',diameter:'51.118 km · equatorial',year:'84 anos terrestres',atmosphere:'Hidrogênio, hélio e metano',fact:'Seu eixo muito inclinado faz o planeta girar quase de lado.',source:'https://science.nasa.gov/uranus/facts/'},
 neptune:{name:'Netuno',type:'Gigante de gelo',diameter:'49.528 km · equatorial',year:'165 anos terrestres',atmosphere:'Hidrogênio, hélio e metano',fact:'Foi previsto por cálculos matemáticos antes de ser observado.',source:'https://science.nasa.gov/neptune/neptune-facts/'},
 moon:{name:'Lua',type:'Satélite natural da Terra',diameter:'3.475 km',year:'Órbita: 27,3 dias',atmosphere:'Exosfera muito tênue',fact:'Sua rotação sincronizada mantém praticamente a mesma face voltada para a Terra.',source:'https://science.nasa.gov/moon/facts/'},
 sun:{name:'Sol',type:'Estrela',diameter:'1,39 milhão de km',year:'Rotação diferencial',atmosphere:'Fotosfera, cromosfera e coroa',fact:'A energia do Sol vem da fusão nuclear em seu interior.',source:'https://science.nasa.gov/sun/facts/'}
};

export function fillPlanetFacts(element,id) {
 const fact=PLANET_FACTS[id];if(!fact)return;
 element.querySelector('strong').textContent=fact.name;
 element.querySelector('.planet-kind').textContent=fact.type;
 const list=element.querySelector('dl');list.replaceChildren();
 for(const [label,value] of [['Diâmetro',fact.diameter],[id==='moon'?'Período orbital':id==='sun'?'Rotação':'Ano',fact.year],['Atmosfera',fact.atmosphere]]) {
  const term=document.createElement('dt'),detail=document.createElement('dd');term.textContent=label;detail.textContent=value;list.append(term,detail);
 }
 element.querySelector('.planet-fact').textContent=fact.fact;
 element.dataset.planet=id;
}
