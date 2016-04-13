// https://docs.google.com/spreadsheets/d/1P4hjCU6wEyKbcaReW8YNloIQvvW2BX4bQz1CxvWn4V0/edit
// https://script.google.com/a/yanofsky.org/macros/d/1HPzNAlAl2uhXp4HvVyxxZ-9kbzKz43EnMm-RD51wyMSVNV37o14ACoVD/edit
food = {
  bo: [5, 0],                           // boullion
  cab: [31.0/100, 0],                   // red cabbage g
  car: [35.0/100, 0],                   // carrot g
  chick: [500, 105],                    // chicken lb
  choc: [10.0/5, 0],                    // choc g
  crispix: [110.0/29, 0],               // crispix g
  egg: [70*91.0/78, 6],                 // scrambled egg
  kashi: [190.0/53, 9.0/53],            // golean crunch g
  let: [14.0/100, 0],                   // iceberg lettuce g
  meal: [400, 20],                      // mealsquare
  moz: [80 * 32.0/907, 8 * 32.0/907],   // moz cheese g
  multich: [110.0/29, 0],               // cheerios g (multich)
  nvap: [190, 10],                      // nature valley "Peanut, Almond & Dark Chocololate"
  nvpa: [160, 3],                       // nature valley "Dark Chocolate Peanut & Almond" "Dipped in Chocolate Flavored Coating Bursting with Dark Chocolate & Nuts!" "Sweet & Salty Nut"
  nvpb: [190, 10],                      // nature valley "Peanut Butter Dark Chocolate" "Protein"
  nvpr: [150, 2],                       // nature valley "Chocolate Pretzel Nut" "dipped in chocolate flavored coating busting with pretzels and almonds" "Sweet & Salty Nut"
  p: [190.0/32, 7.0/32],                // peanut butter g
  pb: [45.0/12, 5.0/12],                // pb2 g
  pita: [210, 0],                       // pita bread
  psy: [20, 0],                         // psyllium
  relish: [20.0/15, 0],                 // relish g
  rom: [17.0/100, 0],                   // romain lettuce g
  sal: [60, 0],                         // salad bag
  soy: [500.0/115, 20.0/115],           // soylent g
  sweetp: [0.9, 0],                     // sweet potato g
  tom: [70 * 15.0/1900, 0],//2 * 15.0/1900], // tomato sauce g
  tuna: [90, 20],                       // tuna can
  whey: [120.0/31.5, 24.0/31.5],        // whey rocky road g
  wheycc: [130.0/33, 24.0/33],          // whey cookies n creme g
}

function sumexpr(expr, column) {
  var parts = expr.split(/ /);
  var sum = 0.0;
  for (var i = 0; i < parts.length; ++i) {
    part = parts[i];
    if (!part) continue;
    match = /^([0-9.]+)(?:\/([0-9.]+))?([a-z]+)$/.exec(part);
    if (!match) throw new Error("could not parse subexpr: '" + part + "'");
    var num = Number(match[1]);
    var den = match[2] ? Number(match[2]) * 1.0 : 1.0;
    var name = match[3];
    if (!(name in food)) throw new Error("unknown food '" + part + "'");
     sum += Number(num / den * food[name][column]);
  }
  return sum;
}


function calories(expr) {
  return sumexpr(expr, 0);
}

function protein(expr) {
  return sumexpr(expr, 1);
}

function upgrade() {
  var sheet = SpreadsheetApp.getActiveSheet();
  sheet.insertColumnsBefore(12, 3);
  sheet.getRange(1, 12).setValue("Foods");
  sheet.getRange(1, 13).setValue("+Calories");
  sheet.getRange(1, 14).setValue("+Protein");
  sheet.insertColumnsAfter(16, 2);
  var rows = sheet.getMaxRows();
  for (var row = 2; row <= rows; ++row) {
    if (row == 195 || row == 199) continue;
    var foods = ""
    foods = addFood(sheet, row, 7, "soy", foods);
    foods = addFood(sheet, row, 8, "pb", foods);
    foods = addFood(sheet, row, 9, "whey", foods);
    foods = addFood(sheet, row, 10, "chick", foods);
    foods = addFood(sheet, row, 11, "egg", foods);
    var cal = breakFormula(sheet, row, 15, foods);
    var prot = breakFormula(sheet, row, 16, foods);
    sheet.getRange(row, 12).setValue(cal.foods);

    var oldcal = sheet.getRange(row, 15).getValue();
    var oldprot = sheet.getRange(row, 16).getValue();
    if (oldcal == "" && oldprot == "") continue;

    if (cal.extra) sheet.getRange(row, 13).setFormula(cal.extra);
    if (prot.extra) sheet.getRange(row, 14).setFormula(prot.extra);
    var calform = "=calories(L" + row + ") + M" + row;
    var protform = "=protein(L" + row + ") + N" + row;
    sheet.getRange(row, 17).setFormula(calform);
    sheet.getRange(row, 18).setFormula(protform);
    var newcal = sheet.getRange(row, 17).getValue();
    var newprot = sheet.getRange(row, 18).getValue();
    if (Math.abs(oldcal - newcal) > 0.001 || Math.abs(oldprot - newprot) > 0.001) {
      msg = "fucked up row " + row + ", cal " + oldcal + "=>" + newcal + ", prot " + oldprot + "=>" + newprot;
      Logger.log(msg);
      if (row != 20 && row != 26 && row != 91 && row != 126 && row != 130 && row != 159 && row != 160 && row != 173 && row != 175 && row != 188 && row != 191 && row != 196 && row != 198) throw new Error(msg);
    }
    sheet.getRange(row, 15).setFormula(calform);
    sheet.getRange(row, 16).setFormula(protform);
  }
  sheet.deleteColumns(17, 2);
}

function breakFormula(sheet, row, col, foods) {
  var extra = "";
  var formula = sheet.getRange(row, col).getFormula();
  formula = formula.replace(/^=G[0-9]+\*soyp? \+ H[0-9]+\*pbp? \+ (?:I[0-9]+\*wheyp? \+ )?J[0-9]+\*chickp?(?: \+ K[0-9]+\*eggp?)?(?: *\+ *)?/, "");
  formula = formula.replace(/(?:^=?|\+) *([0-9]*\*?iferror\([^"]+"[^"]+"\))/gi, function(whole, iferr) {
    if (extra) extra += " + ";
    extra += iferr;
    return "";
  });

  var parts = formula.split(/ *\+ */);
  for (var i = 0; i < parts.length; ++i) {
    part = parts[i];
    if (!part || /^ +$/.exec(part)) continue;
    match = /^([0-9.]+)?(?:\/([0-9.]+))? *\*? *([a-z]+)(?:\/([0-9.]+))?(?:\*([0-9.]+))?(?:\/([0-9.]+))? *$/.exec(part);
    if (!match) throw new Error("could not parse subexpr: '" + part + "' row " + row);
    var num = match[1];
    var den = match[2];
    var name = match[3];
    var den2 = match[4];
    var num2 = match[5];
    var den3 = match[6];
    if (!(name in food) && name.slice(-1) == "p") name = name.slice(0, -1);
    if (!(name in food)) throw new Error("unknown food '" + name + "' in part '" + part + "'");
    if (foods) foods += " ";
    if (num) {
    if (num2) throw new Error("num2");
      foods += num;
    } else if (num2) {
      foods += num2;
    } else {
      foods += 1;
    }
    if (den) foods += "/" + den;
    if (den2) foods += "/" + den2;
    if (den3) foods += "/" + den3;
    foods += name;
  }

  return { foods: foods, extra: extra.length > 0 ? "=" + extra : ""};
}

function addFood(sheet, row, col, food, foods) {
  var range = sheet.getRange(row, col);
  var formula = range.getFormula();
  if (formula.length == 0) {
    var value = range.getValue();
    if (value) {
      if (foods.length > 0) foods += " ";
      foods += value + food;
    }
  } else {
    var parts = formula.split(/ *\+ */);
    for (var i = 0; i < parts.length; ++i) {
      var part = parts[i];
      var match = /^=?([0-9.]+)$/.exec(part);
      if (!match) throw new Error("could not match part '" + part + "'");
      if (foods.length > 0) foods += " ";
      foods += match[1] + food;
    }
  }
  return foods;
}


function printranges() {
  var ssheet = SpreadsheetApp.getActiveSpreadsheet();
  var ranges = ssheet.getNamedRanges();
  for (var i = 0; i < ranges.length; ++i) {
    var nrange = ranges[i];
    var name = nrange.getName();
    var range = nrange.getRange();
    if (range.getNumRows() == 1 && range.getNumColumns() == 1) {
      var formula = range.getFormula();
      if (formula.length > 0) {
        Logger.log(name + " formula '" + formula + "' " + formula.length);
      } else {
        var value = range.getValue();
        Logger.log(name + " val '" + value + "' ");
      }
    }
  }
}

function killranges() {
  var ssheet = SpreadsheetApp.getActiveSpreadsheet();
  var ranges = ssheet.getNamedRanges();
  for (var i = 0; i < ranges.length; ++i) {
    var nrange = ranges[i];
    var name = nrange.getName();
    if (name in food || (name.slice(-1) == "p" && name.slice(0, -1) in food)) {
      Logger.log("kill range " + name);
      nrange.remove();
    }
  }
}
