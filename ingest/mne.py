#---------------------------
# Based on this system:
# http://gurno.com/adam/mne/
#---------------------------
class Mne:
  
  DATAA = [           
           "zip", "ace", "act", "add", "age",
           "aim", "air", "and", "ant", "ape",
           "arm", "art", "ash", "ask", "bad",
           "bag", "ban", "bar", "bat", "bay",
           "bed", "bet", "bid", "big", "bin",
           "bit", "bog", "boo", "box", "bud",
           "bug", "bun", "bus", "cab", "can",
           "cap", "car", "cat", "cop", "cot",
           "cow", "cry", "cub", "cup", "cut",
           "day", "den", "did", "die", "dig",
           "dim", "dip", "dog", "dry", "dub",
           "dud", "dug", "ear", "eat", "eel",
           "egg", "elf", "elk", "elm", "end",
           "fan", "far", "fat", "fed", "few",
           "fib", "fig", "fin", "fit", "fix",
           "fly", "fog", "foo", "fox", "fry",
           "fun", "gab", "gag", "gap", "gas",
           "gel", "gem", "get", "gin", "got",
           "gum", "gut", "had", "has", "hat",
           "hen", "hex", "hid", "hip", "hit",
           "hog", "hop", "hot", "how", "hub",
           "hug", "hum", "hut", "ice", "ill",
           "imp", "ink", "irk", "jab", "jam",
           "jar", "jaw", "jet", "jig", "job",
           "jog", "jot", "joy", "key", "kid",
           "kin", "kit", "lab", "lag", "lap",
           "law", "lax", "lay", "leg", "let",
           "lid", "lip", "lit", "lot", "low",
           "mad", "map", "mat", "men", "met",
           "mix", "mob", "moo", "mop", "mud",
           "mug", "nab", "nag", "nap", "net",
           "new", "nil", "nip", "nod", "nor",
           "now", "nut", "oak", "oat", "odd",
           "off", "old", "orb", "out", "owl",
           "own", "pad", "pal", "pan", "pay",
           "pen", "pet", "pie", "pig", "pin",
           "pit", "ply", "pod", "pop", "pot",
           "pox", "pry", "pun", "pup", "put",
           "rag", "ran", "rat", "raw", "red",
           "rid", "rig", "rip", "rot", "row",
           "rub", "rug", "run", "rut", "rye",
           "sad", "sag", "sap", "sat", "saw",
           "say", "set", "shy", "sip", "sit",
           "ski", "sky", "sly", "sob", "soy",
           "spa", "spy", "tab", "tag", "tan",
           "tap", "tar", "tax", "the", "tie",
           "tin", "tip", "top", "toy", "try",
           "tub", "tug", "use", "van", "vat",
           "vex", "vow", "wag", "war", "was",
           "wax", "web", "wet", "who", "wig",
           "win", "wit", "yes", "yet", "zoo",
           "all"]
  
  DATAD = {
           "zip" : "000", "ace" : "001", "act" : "002", "add" : "003", "age" : "004",
           "aim" : "005", "air" : "006", "and" : "007", "ant" : "008", "ape" : "009",
           "arm" : "010", "art" : "011", "ash" : "012", "ask" : "013", "bad" : "014",
           "bag" : "015", "ban" : "016", "bar" : "017", "bat" : "018", "bay" : "019",
           "bed" : "020", "bet" : "021", "bid" : "022", "big" : "023", "bin" : "024",
           "bit" : "025", "bog" : "026", "boo" : "027", "box" : "028", "bud" : "029",
           "bug" : "030", "bun" : "031", "bus" : "032", "cab" : "033", "can" : "034",
           "cap" : "035", "car" : "036", "cat" : "037", "cop" : "038", "cot" : "039",
           "cow" : "040", "cry" : "041", "cub" : "042", "cup" : "043", "cut" : "044",
           "day" : "045", "den" : "046", "did" : "047", "die" : "048", "dig" : "049",
           "dim" : "050", "dip" : "051", "dog" : "052", "dry" : "053", "dub" : "054",
           "dud" : "055", "dug" : "056", "ear" : "057", "eat" : "058", "eel" : "059",
           "egg" : "060", "elf" : "061", "elk" : "062", "elm" : "063", "end" : "064",
           "fan" : "065", "far" : "066", "fat" : "067", "fed" : "068", "few" : "069",
           "fib" : "070", "fig" : "071", "fin" : "072", "fit" : "073", "fix" : "074",
           "fly" : "075", "fog" : "076", "foo" : "077", "fox" : "078", "fry" : "079",
           "fun" : "080", "gab" : "081", "gag" : "082", "gap" : "083", "gas" : "084",
           "gel" : "085", "gem" : "086", "get" : "087", "gin" : "088", "got" : "089",
           "gum" : "090", "gut" : "091", "had" : "092", "has" : "093", "hat" : "094",
           "hen" : "095", "hex" : "096", "hid" : "097", "hip" : "098", "hit" : "099",
           "hog" : "100", "hop" : "101", "hot" : "102", "how" : "103", "hub" : "104",
           "hug" : "105", "hum" : "106", "hut" : "107", "ice" : "108", "ill" : "109",
           "imp" : "110", "ink" : "111", "irk" : "112", "jab" : "113", "jam" : "114",
           "jar" : "115", "jaw" : "116", "jet" : "117", "jig" : "118", "job" : "119",
           "jog" : "120", "jot" : "121", "joy" : "122", "key" : "123", "kid" : "124",
           "kin" : "125", "kit" : "126", "lab" : "127", "lag" : "128", "lap" : "129",
           "law" : "130", "lax" : "131", "lay" : "132", "leg" : "133", "let" : "134",
           "lid" : "135", "lip" : "136", "lit" : "137", "lot" : "138", "low" : "139",
           "mad" : "140", "map" : "141", "mat" : "142", "men" : "143", "met" : "144",
           "mix" : "145", "mob" : "146", "moo" : "147", "mop" : "148", "mud" : "149",
           "mug" : "150", "nab" : "151", "nag" : "152", "nap" : "153", "net" : "154",
           "new" : "155", "nil" : "156", "nip" : "157", "nod" : "158", "nor" : "159",
           "now" : "160", "nut" : "161", "oak" : "162", "oat" : "163", "odd" : "164",
           "off" : "165", "old" : "166", "orb" : "167", "out" : "168", "owl" : "169",
           "own" : "170", "pad" : "171", "pal" : "172", "pan" : "173", "pay" : "174",
           "pen" : "175", "pet" : "176", "pie" : "177", "pig" : "178", "pin" : "179",
           "pit" : "180", "ply" : "181", "pod" : "182", "pop" : "183", "pot" : "184",
           "pox" : "185", "pry" : "186", "pun" : "187", "pup" : "188", "put" : "189",
           "rag" : "190", "ran" : "191", "rat" : "192", "raw" : "193", "red" : "194",
           "rid" : "195", "rig" : "196", "rip" : "197", "rot" : "198", "row" : "199",
           "rub" : "200", "rug" : "201", "run" : "202", "rut" : "203", "rye" : "204",
           "sad" : "205", "sag" : "206", "sap" : "207", "sat" : "208", "saw" : "209",
           "say" : "210", "set" : "211", "shy" : "212", "sip" : "213", "sit" : "214",
           "ski" : "215", "sky" : "216", "sly" : "217", "sob" : "218", "soy" : "219",
           "spa" : "220", "spy" : "221", "tab" : "222", "tag" : "223", "tan" : "224",
           "tap" : "225", "tar" : "226", "tax" : "227", "the" : "228", "tie" : "229",
           "tin" : "230", "tip" : "231", "top" : "232", "toy" : "233", "try" : "234",
           "tub" : "235", "tug" : "236", "use" : "237", "van" : "238", "vat" : "239",
           "vex" : "240", "vow" : "241", "wag" : "242", "war" : "243", "was" : "244",
           "wax" : "245", "web" : "246", "wet" : "247", "who" : "248", "wig" : "249",
           "win" : "250", "wit" : "251", "yes" : "252", "yet" : "253", "zoo" : "254",
           "all" : "255" }
  
  def  num_to_mne(num):
       
       #-----------------------------------
       #store 256 decoded elements in stack
       #-----------------------------------
       stack=[]
       q=num
       if q < 256 :
          q,r = divmod(num,256)
          stack.append(r)
          #print(q,r)       
       else:
           while q > 255 :
               q,r = divmod(q,256)
               stack.append(r)
           stack.append(q)
       #----------------------
       #Finally code the stack
       #----------------------
       rstring=""
       first=True
       for element in reversed(stack):
           if first:
             first=False
           else:
             rstring=rstring + '-'
           rstring=rstring+Mne.DATAA[element]
       #print ("R:",stack)
       rstring="swc_"+rstring
       return rstring
  
  @staticmethod
  def  dataset_num_to_mne(num):
       
       #-----------------------------------
       #store 256 decoded elements in stack
       #-----------------------------------
       stack=[]
       q=num
       if q < 256 :
          q,r = divmod(num,256)
          stack.append(r)     
       else:
           while q > 255 :
               q,r = divmod(q,256)
               stack.append(r)
           stack.append(q)
       #----------------------
       #Finally code the stack
       #----------------------
       rstring=""
       first=True
       for element in reversed(stack):
           if first:
             first=False
           else:
             rstring=rstring + '-'
           rstring=rstring+Mne.DATAA[element]
       return rstring

  def  mne_to_num(mme):
       stack=[]
       values=mme.split('-')
       for i in values:
          stack.append(int(Mne.DATAD[i]))
       vsum=0
       value=0
       for i in range(0,len(stack)-1,1):
          vsum=256**(len(stack)-i-1) * stack[i] + vsum
       vsum=vsum+stack[len(stack)-1]
       return(vsum)   

  def mne_test(self):
      #Simple Test code for MNE:
      mne = Mne()
      testvalues=[5,255,256,257,511,512,513,65535,65536,65537,16777215,16777216,16777217]
      for i in testvalues:
          vv=self.num_to_mne(i)
          print("Coding: ", i, vv)
          print("Deconding: ",vv, mne.mne_to_num(vv))


