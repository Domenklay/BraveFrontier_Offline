package com.domenklay.bravefrontieroffline;

import android.content.Context;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

final class GameData {
    static final String[] ELEMENTS = {"fire", "water", "earth", "thunder", "light", "dark"};

    static class Unit {
        final String id, name, element;
        final int hp, atk, def;
        Unit(String id, String name, String element, int hp, int atk, int def) {
            this.id=id; this.name=name; this.element=element;
            this.hp=hp; this.atk=atk; this.def=def;
        }
        static Unit parse(JSONObject j) throws JSONException {
            return new Unit(identifier(j.getString("id")), title(j.getString("name")),
                    element(j.getString("element")), value(j, "hp", 1, 99999),
                    value(j, "atk", 1, 9999), value(j, "def", 0, 9999));
        }
        JSONObject json() throws JSONException {
            return new JSONObject().put("id",id).put("name",name).put("element",element)
                    .put("hp",hp).put("atk",atk).put("def",def);
        }
    }
    static class Mode {
        final String id, name, description, element;
        final int waves, enemyHp, enemyAtk, reward;
        Mode(String id,String name,String description,int waves,int hp,int atk,String element,int reward) {
            this.id=id;this.name=name;this.description=description;this.waves=waves;
            this.enemyHp=hp;this.enemyAtk=atk;this.element=element;this.reward=reward;
        }
        static Mode parse(JSONObject j) throws JSONException {
            return new Mode(identifier(j.getString("id")),title(j.getString("name")),
                    j.optString("description",""),value(j,"waves",1,50),
                    value(j,"enemyHp",10,999999),value(j,"enemyAtk",1,9999),
                    element(j.getString("element")),value(j,"reward",0,1000000));
        }
        JSONObject json() throws JSONException {
            return new JSONObject().put("id",id).put("name",name)
                    .put("description",description).put("waves",waves)
                    .put("enemyHp",enemyHp).put("enemyAtk",enemyAtk)
                    .put("element",element).put("reward",reward);
        }
    }
    final List<Unit> units = new ArrayList<>();
    final List<Mode> modes = new ArrayList<>();
    final SharedPreferences prefs;
    private final List<Unit> customUnits=new ArrayList<>();
    private final List<Mode> customModes=new ArrayList<>();

    GameData(Context context) throws Exception {
        prefs=context.getSharedPreferences("offline_profile_v1",Context.MODE_PRIVATE);
        StringBuilder raw=new StringBuilder();
        try(BufferedReader reader=new BufferedReader(new InputStreamReader(
                context.getAssets().open("content.json"), StandardCharsets.UTF_8))) {
            String line;
            while((line=reader.readLine())!=null) raw.append(line);
        }
        JSONObject bundled=new JSONObject(raw.toString());
        readUnits(bundled.optJSONArray("units"),units,new HashSet<>());
        readModes(bundled.optJSONArray("modes"),modes,new HashSet<>());
        JSONObject custom=new JSONObject(prefs.getString("custom_pack","{}"));
        Set<String> unitIds=new HashSet<>(), modeIds=new HashSet<>();
        for(Unit u:units) unitIds.add(u.id);
        for(Mode m:modes) modeIds.add(m.id);
        readUnits(custom.optJSONArray("units"),customUnits,unitIds);
        readModes(custom.optJSONArray("modes"),customModes,modeIds);
        units.addAll(customUnits);modes.addAll(customModes);
        if(units.size()<6 || modes.isEmpty()) throw new IllegalStateException("Missing starter content");
    }

    static String identifier(String s) throws JSONException {
        if(s==null || !s.matches("[a-zA-Z0-9_-]{1,40}")) throw new JSONException("Invalid id (1–40: a-z 0-9 _ -)");
        return s;
    }
    static String title(String s) throws JSONException {
        if(s==null || s.trim().isEmpty() || s.length()>60) throw new JSONException("Name must be 1–60 characters");
        return s.trim();
    }
    static String element(String s) throws JSONException {
        for(String e:ELEMENTS) if(e.equals(s))return s;
        throw new JSONException("Unknown element: "+s);
    }
    static int value(JSONObject j,String field,int min,int max) throws JSONException {
        int n=j.getInt(field);
        if(n<min || n>max)throw new JSONException(field+" must be "+min+".."+max);
        return n;
    }
    private static void readUnits(JSONArray a,List<Unit> destination,Set<String> ids) throws JSONException {
        if(a==null)return;
        if(a.length()>1000)throw new JSONException("Too many units");
        for(int i=0;i<a.length();i++){
            Unit u=Unit.parse(a.getJSONObject(i));
            if(!ids.add(u.id))throw new JSONException("Duplicate unit id: "+u.id);
            destination.add(u);
        }
    }
    private static void readModes(JSONArray a,List<Mode> destination,Set<String> ids) throws JSONException {
        if(a==null)return;
        if(a.length()>1000)throw new JSONException("Too many modes");
        for(int i=0;i<a.length();i++){
            Mode m=Mode.parse(a.getJSONObject(i));
            if(!ids.add(m.id))throw new JSONException("Duplicate mode id: "+m.id);
            destination.add(m);
        }
    }
    private void saveCustom() throws JSONException {
        prefs.edit().putString("custom_pack",exportCustom()).apply();
    }
    String exportCustom() throws JSONException {
        JSONObject out=new JSONObject().put("schema",1);
        JSONArray u=new JSONArray(),m=new JSONArray();
        for(Unit x:customUnits)u.put(x.json());
        for(Mode x:customModes)m.put(x.json());
        return out.put("units",u).put("modes",m).toString(2);
    }
    int importPack(String text) throws JSONException {
        JSONObject json=new JSONObject(text);
        if(json.optInt("schema",1)!=1)throw new JSONException("Unsupported schema");
        List<Unit> addUnits=new ArrayList<>();
        List<Mode> addModes=new ArrayList<>();
        Set<String> unitIds=new HashSet<>(),modeIds=new HashSet<>();
        for(Unit u:units)unitIds.add(u.id);
        for(Mode m:modes)modeIds.add(m.id);
        readUnits(json.optJSONArray("units"),addUnits,unitIds);
        readModes(json.optJSONArray("modes"),addModes,modeIds);
        if(addUnits.isEmpty()&&addModes.isEmpty())throw new JSONException("Empty pack");
        customUnits.addAll(addUnits);customModes.addAll(addModes);
        units.addAll(addUnits);modes.addAll(addModes);
        saveCustom();
        return addUnits.size()+addModes.size();
    }
    void addUnit(Unit unit) throws JSONException {
        for(Unit u:units)if(u.id.equals(unit.id))throw new JSONException("Unit id already exists");
        customUnits.add(unit);units.add(unit);saveCustom();
    }
    void addMode(Mode mode) throws JSONException {
        for(Mode m:modes)if(m.id.equals(mode.id))throw new JSONException("Mode id already exists");
        customModes.add(mode);modes.add(mode);saveCustom();
    }
    Unit getUnit(String id) {
        for(Unit u:units)if(u.id.equals(id))return u;
        return null;
    }
    Mode getMode(String id) {
        for(Mode m:modes)if(m.id.equals(id))return m;
        return null;
    }
    List<Unit> squad() {
        List<Unit> result=new ArrayList<>();
        JSONArray ids;
        try {ids=new JSONArray(prefs.getString("team","[]"));}catch(JSONException e){ids=new JSONArray();}
        for(int i=0;i<6;i++){
            Unit selected=i<ids.length()?getUnit(ids.optString(i)):null;
            if(selected==null || result.contains(selected)) {
                for(Unit candidate:units)if(!result.contains(candidate)){selected=candidate;break;}
            }
            if(selected!=null)result.add(selected);
        }
        return result;
    }
    void selectUnit(int slot,String id) throws JSONException {
        if(slot<0||slot>5 || getUnit(id)==null)throw new JSONException("Invalid slot or unit");
        List<Unit> current=squad();
        for(int i=0;i<current.size();i++)if(i!=slot && current.get(i).id.equals(id)){
            throw new JSONException("Unit already assigned to another slot");
        }
        current.set(slot,getUnit(id));
        JSONArray a=new JSONArray();
        for(Unit u:current)a.put(u.id);
        prefs.edit().putString("team",a.toString()).apply();
    }
    int gold(){return prefs.getInt("gold",0);}
    int victories(){return prefs.getInt("victories",0);}
    void reward(int amount){
        prefs.edit().putInt("gold",gold()+amount).putInt("victories",victories()+1).apply();
    }
    String savedBattle(){return prefs.getString("battle","");}
    void saveBattle(Battle b){prefs.edit().putString("battle",b==null?"":b.toJson()).apply();}
}
