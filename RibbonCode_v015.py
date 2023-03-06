"""
Der folgende Quelltext erstellt ein automatisiertes Tool zur 
Erstellung eines Rigges für den Mund.
Dieser Quelltext ist im Rahmen der Bachelorarbeit mit dem Thema 
"Entwicklung eines automatisierten Rigging Tools zum Riggen eines 
Mundes nach Betrachtung und Bewertung zweier gängigen Rigging 
Frameworks in Maya" entstanden.
Für diesen Quelltext wurden ausschließlich bekannte Funktionen 
verwendet. Er beinhaltet keine außergewöhnlichen Ideen 
anderer Personen.
Stand: 15.08.2022
Verfasserin: Vanessa Stotz
"""
import pymel.core as pm
from pymel.core.datatypes import Vector
from PySide2 import QtCore, QtWidgets
from shiboken2 import wrapInstance
import maya.OpenMayaUI as omui


"""
Diese Funktion konvertiert den ausgewählten Edge-Loop 
in eine NURBS-Kurve.
Sie erwartet einen Edge-Loop, das definierte Präfix sowie die 
Nummer der NURBS-Kurve.
Durch polyToCurve wird der Edge-Loop in eine NURBS-Kurve konvertiert
Die erstellte NURBS-Kurve wird wieder zurückgegeben.
"""
def get_edge_curve(selectedEdge, prefix: str="", numCurve: int=0):

    pm.select(selectedEdge, replace=True)
    curve = pm.polyToCurve(constructionHistory=0, form=2, degree=3, 
                conformToSmoothMeshPreview=0, 
                name = f"{prefix}_00{numCurve}_crv" )
    curve = pm.rebuildCurve(curve, constructionHistory=0,
                replaceOriginal=1, rebuildType=0, endKnots=1,
                keepRange=0, keepControlPoints=1, 
                keepEndPoints=1, keepTangents=0, degree=3)[0]
    pm.select(clear=True)

    return curve

"""
Diese Funktion bestimmt die Anzahl der erstellten Follicles und 
der deformierenden Joints. Sie erwartet als Eingabe den 
ausgewählten Edge-Loop. 
Durch polyEvaluate werden die Edges, aus denen der 
Edge-Loop besteht, gezählt.
Diese Zahl wird wieder zurückgegeben.
"""
def get_edge_count(selectedEdge):

    pm.select(selectedEdge, replace = True)
    edge_count = pm.polyEvaluate(edgeComponent=True)
    pm.select(clear=True)

    return edge_count


"""
Diese Funktion passt den Startpunkt der Kurven an 
den ausgewählten Vertexpunkt an.
Sie erwartet als Eingabe eine NURBS-Kurve sowie 
die Position des Vertexpunktes.
Die nearestPointOnCurve Node bestimmt den naheliegendsten 
Punkt zum Vertexpunkt.
Dieser wird ausgewählt und durch MoveCurveSeam als 
Startpunkt festgelegt.
Die veränderte Kurve wird wieder zurückgegeben
"""
def move_Seam(vertex_position, crv):

    nearest_point_node = pm.createNode("nearestPointOnCurve")
    nearest_point_node.inPosition.set(vertex_position)
    crv.getShape().attr("worldSpace[0]") >> \
                        nearest_point_node.inputCurve
    pm.select(crv.u[nearest_point_node.parameter.get()], replace=True)
    pm.mel.eval("MoveCurveSeam;")
    pm.delete(nearest_point_node)
    pm.select(clear = True)

    return crv

"""
Diese Funktion bestimmt den Abstand zwischen den zwei Kurven und 
definiert dadurch die Größe der Joints und Controller.
Sie erwartet als Eingabe die beiden NURBS-Kurven.
Durch pointOnCurveInfo wird die Position eines Punktes auf 
der Kurve bestimmt, dieser wird in einem Vektor gespeichert. 
Um die Größe zu definieren, wird der Abstand zwischen den 
beiden Punkten gemessen.
Der Wert der Größe wird zurückgegeben.
"""
def get_reference_size(crv_1, crv_2):
    
    size_node = pm.createNode("pointOnCurveInfo")
    crv_1.getShape().attr("worldSpace[0]") >> size_node.inputCurve
    crv_1_vector = Vector(size_node.position.get())
    crv_2.getShape().attr("worldSpace[0]") >> size_node.inputCurve
    crv_2_vector = Vector(size_node.position.get())

    size = crv_1_vector.distanceTo(crv_2_vector)

    pm.delete(size_node)

    return size

"""
Diese Funktion erstellt die NURBS-Regelfläche.
Sie erwartet als Eingabe die beiden NURBS-Kurven, den Vertexpunkt 
sowie das Präfix. Zuerst wird der Anfangspunkt der beiden 
NURBS-Kurven durch Aufruf der Funktion move_seam() angepasst. 
Danach wird durch pm.loft() die NURBS-Regelfläche erstellt. 
Die NURBS-Regefläche wird auf die UV-Verteilung und 
Invertierung getestet.
Die erstellte NURBS-Regelfläche wird zurückgegeben.
"""

def get_lofted_surface(crvSeam_1, crvSeam_2, vertex, prefix: str=""):
    
    # Speichert die Position des Vertexpunktes in 
    # der Variable position, passt die Anfangspunkte an 
    # und erstellt die NURBS-Regelfläche.
    position = pm.pointPosition(vertex)
    crv_1 = move_Seam(position, crvSeam_1)
    crv_2 = move_Seam(position, crvSeam_2)
    lofted_surface, loft = pm.loft(crv_1, crv_2, 
                                name= f"{prefix}_001_NURBSPlane",
                                degree=1)

    # Überpüft, ob sich die Auflösung auf den U-Werten befindet.
    spans = lofted_surface.spansUV.get()
    if spans[0] < spans[1]:
        loft.reverseSurfaceNormals.set(True)
    
    # Löscht die History der NURBS-Regelfläche
    pm.delete(lofted_surface, ch=True)
   
    # Bestimmt einen Punkt auf der NURBS-Regelfläche und vergleicht
    # diesen mit dem Einheitsvektor in Z-Richtung.
    point_info = pm.createNode("pointOnSurfaceInfo")
    lofted_surface.getShape().attr("worldSpace[0]") >> \
                                    point_info.inputSurface
    dot = Vector.dot([0,0,1],point_info.result.normal.get())

    # Sollte das Ergebnis des Skalarproduktes negativ sein, 
    # wird die NURBS-Regelfläche invertiert.
    if dot < 0 :
        pm.reverseSurface(lofted_surface)
    
    # Löscht die erstellte pointOnSurfaceInfo Node.
    pm.delete(point_info)

    return lofted_surface

"""
Diese Funktion erstellt die Follicles und deformierenden Joints 
entlang der NURBS-Regelfläche. Sie erwartet als Eingabe 
die NURBS-Regelfläche, das Präfix, die Gruppe für die Follicles,
deformierenden Joints, die bereits definierte Anzahl der 
benötigten Follicles und Joints sowie die bereits definierte Größe. 
Die Funktion gibt keinen Wert zurück.
"""

def create_surface_ribbons(lofted_surface, prefix, follicle_grp, 
                                    binding_joint_grp, u_count, size):

    # Die For-Schleife iteriert über die Anzahl der 
    # benötigten Follicles und deformierenden Joints.
    for i in range(u_count):

        # Erstellt einen Follicle.
        fol_rbn = pm.createNode('transform', 
                            name=f"{prefix}_rbn_{i+1}_fol", 
                            skipSelect=True)
        folShape_rbn = pm.createNode('follicle' ,
                            name=fol_rbn.name()+'Shape',
                            parent=fol_rbn, skipSelect=True)
        folShape_rbn.outRotate >> fol_rbn.rotate
        folShape_rbn.outTranslate >> fol_rbn.translate
        lofted_surface.worldMatrix >> fol_rbn.inputWorldMatrix
        lofted_surface.local >> fol_rbn.inputSurface

        # Setzt die Position des Follicles an die gewünschte Stelle.
        folShape_rbn.parameterU.set(0+(1.0/u_count) * i)
        folShape_rbn.parameterV.set(0.5)

        # Erstellt einen Joint.
        rbn_joint = pm.joint(radius = size/3, 
                            name =f"{prefix}_{i+1}_bnd_jnt")
        
        # Legt den Follicle und den Joint in die zugehörige Gruppe. 
        pm.parent(rbn_joint , binding_joint_grp)
        pm.parent(fol_rbn, follicle_grp)

        # Macht den Joint durch einen Parent-Constraint
        # für die Transformation sowie einen Orient-Constraint 
        # für die Rotation vom Follicle abhängig.
        pm.parentConstraint(fol_rbn , rbn_joint ,
                                skipRotate=['x','y','z'], 
                                maintainOffset = 0 , weight=1)
        pm.orientConstraint(fol_rbn , rbn_joint , maintainOffset = 0)
        pm.select(clear=1)

"""
Diese Funktion berechnet den U-Wert anhand der X,Y,Z Koordinaten
des Hüllkörpers. Sie erwartet als Eingabe die X,Y und Z Koordinate 
des Hüllkörpers sowie die NURBS-Regelfläche.
Durch die closestPointOnSurface Node wird der U-Wert berechnet.
Dieser wird zurückgegeben.
""" 
def get_corner_point(valueX, valueY, valueZ , lofted_surface):

    nearest_point_node = pm.createNode('closestPointOnSurface')
    lofted_surface.getShape().attr("worldSpace[0]") >> \
                        nearest_point_node.inputSurface
    nearest_point_node.inPositionX.set(valueX)
    nearest_point_node.inPositionY.set(valueY)
    nearest_point_node.inPositionZ.set(valueZ)
    u_value = nearest_point_node.parameterU.get()

    pm.delete(nearest_point_node)

    return u_value

"""
Diese Funktion platziert die kontrollierenden Joints an
den gewünschten Positionen. Sie erwartet als Eingabe 
den U- und V-Wert, die NURBS-Regelfläche sowie das Präfix
und die Größe. 
Die Funktion gibt den erstellten Joint zurück.
""" 
def set_control_joints( u_value , v_value , lofted_surface ,
                        prefix , size ):

    # Erstellt einen Follicle.
    fol = pm.createNode('transform' , name ='follicleCorner', 
                        skipSelect=True)
    folShape = pm.createNode('follicle' , name =fol.name()+'Shape' , 
                        parent=fol, skipSelect=True)
    folShape.outRotate >> fol.rotate
    folShape.outTranslate >> fol.translate
    lofted_surface.worldMatrix >> fol.inputWorldMatrix
    lofted_surface.local >> fol.inputSurface

    # Setzt die Position des Follicles an die gewünschte Stelle.
    folShape.parameterU.set(u_value)
    folShape.parameterV.set(v_value)
    

    # Erstellt einen Joint an der Position des Follicles.
    temp_joint = pm.joint(position = fol.translate.get() , 
                    orientation = fol.rotate.get(),
                    name = f"{prefix}_ctrl_jnt", 
                    radius = size/2)

    # Der Follicle wird nicht weiter benötigt und gelöscht
    pm.delete(fol)
    pm.select(clear = True)

    return temp_joint


"""
Diese Funktion erstellt einen Controller an der Position des Joints. 
Sie erwartet als Eingabe den gewünschten Joint, die Übergruppe
aller Joints sowie die definierte Größe.
Die Funktion gibt keinen Wert zurück.
""" 
def create_controller(joint, main_controller_grp , size):

    # Speichert den Namen des Joints in einer Variablen und 
    # filtert lediglich den Teil vor _jnt heraus. 
    # Dies ist der Name des Controllers.
    jointName = joint.name()
    positionString = jointName.index("_jnt")
    controller_prefix = jointName[0:positionString]

    # Erstellt die Obergruppe und Puffergruppe des Controllers 
    # und legt die Puffergruppe unter die Obergruppe.
    ctrl_grp = pm.group(name = f"{controller_prefix}_grp",
                        empty = True )
    ctrl_buffer_grp = pm.group(
                        name =f"{controller_prefix}_buffer_grp",
                        empty = True)
    pm.parent(ctrl_buffer_grp, ctrl_grp)

    # Erstellt den Controller und legt diesen unter die Puffergruppe.
    controller = pm.circle(name = controller_prefix , radius = size/4)
    pm.parent(controller[0], ctrl_buffer_grp)

    # Setzt die Transformationswerte der Obergruppe des Controllers
    # mit denen des Joints gleich.
    ctrl_grp.translate.set(joint.translate.get())

    # Prüft, ob es sich bei dem erstellten Controller um 
    # einen Seitencontroller handelt, sollte dies nicht der Fall 
    # sein, werden die Rotationswerte der Obergruppe 
    # des Controllers auch mit denen des Joints gleichgesetzt.
    # Die Rotationswerte der seitlichen Joints sind meist extrem und 
    # würden ein Verschwinden des Controllers in 
    # der Geometrie verursachen.
    if jointName.find("_L_") == -1 and jointName.find("_R_") == -1 :
        ctrl_grp.rotate.set(joint.jointOrient.get())

    # Macht den Joint durch einen Parent-Constraint von
    # dem Controller abhängig.
    pm.parentConstraint(controller, joint , maintainOffset = 1)

    # Legt das Konstrukt des Controllers unter
    # die Übergruppe aller Joints
    pm.parent(ctrl_grp, main_controller_grp)

    # Versteckt und sperrt die Attribute zum Skalieren und
    # Ändern der Sichtbarkeit, diese werden nicht benötigt
    # und sollten nicht mehr anwählbar sein.
    controller[0].sx.set(keyable=0, lock = 1)
    controller[0].sy.set(keyable=0, lock = 1)
    controller[0].sz.set(keyable=0, lock = 1)
    controller[0].v.set(keyable=0, lock = 1)

    # Verändert die Farbe der Controller, abhängig davon, 
    # ob diese ein Haupt- oder Nebencontroller sind.
    controller[0].getShape().overrideEnabled.set(True)

    if (jointName.find("_D_")  != -1 or jointName.find("_L_")  != -1 
        or jointName.find("_U_")  != -1
        or jointName.find("_R_")  != -1):
        controller[0].getShape().overrideColor.set(17)
    else:
        controller[0].getShape().overrideColor.set(13)

    # Bewegt den Controller etwas von der Oberfläche
    # der Geometrie weg.
    points = pm.select(f"{controller[0]}.cv[0:7]")
    pm.move(0 , 0 , size/4, points, relative = True, 
                worldSpace = True, worldSpaceDistance = True)

"""
Diese beiden unteren Funktionen erstellen die Abhängigkeiten 
zwischen den Neben- und Hauptcontrollern. 
Die create_blend_for_segment_controller() Funktion erwartet 
als Eingabe das Präfix. Die create_blend() Funktion erwartet 
als Eingabe einen seitlichen- sowie mittleren Hauptcontroller und 
den Namen der Nebencontroller. 
Die Funktionen geben keinen Wert zurück.
""" 
def create_blend_for_segment_controller(prefix):

    # Speichert jeden Hauptcontroller anhand seines Namens
    # in einer Variablen.
    controller_left= pm.ls(f"{prefix}_L_ctrl")
    controller_right= pm.ls(f"{prefix}_R_ctrl")
    controller_middle_up= pm.ls(f"{prefix}_U_ctrl")
    controller_middle_down= pm.ls(f"{prefix}_D_ctrl")

    # Ruft für jedes Segment die create_blend() Funktion auf.
    create_blend(controller_left, controller_middle_up,
                            f"{prefix}_LU_")
    create_blend(controller_left, controller_middle_down,
                            f"{prefix}_LD_")
    create_blend(controller_right, controller_middle_up,
                            f"{prefix}_RU_")
    create_blend(controller_right, controller_middle_down,
                            f"{prefix}_RD_")


def create_blend(side, middle, contains):

    # Speichert alle Controller, welche sich in 
    # diesem Segment befinden, in einer Liste und 
    # bestimmt die Länge der Liste.
    controller_segment =  pm.ls(f"{contains}*_ctrl")
    length = len(controller_segment)

    # Die For-Schleife iteriert für die Anzahl der in der Liste 
    # gespeicherten Controller und setzt die Abhängigkeiten durch 
    # zwei Parent-Constraints mit unterschiedlichen Einflüssen.
    # Die Abhängigkeiten werden auf die Puffergruppe 
    # des Controllers gesetzt.
    for i in range (length):
        value = (1/(length+1))*(i+1)
        controller_temp = f"{controller_segment[i].name()}_buffer_grp"
        pm.parentConstraint(side , controller_temp,
                                maintainOffset = 1,
                                weight=1-value)
        pm.parentConstraint(middle , controller_temp ,
                                maintainOffset = 1,
                                weight=value)
        

"""
Benötigte Funktion, um das Fenster in Maya sichtbar zu machen.
"""
def mayaWindow():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr),QtWidgets.QWidget)

"""
Dies ist die Hauptklasse des Tools.
Sie wird als erstes aufgerufen und ruft im Verlauf alle bereits definierten Funktionen auf.
"""
class ribbon_lip_rigger(QtWidgets.QDialog):
        
    #Konstruktor
    def __init__(self,parent=mayaWindow()):
            
        # Definiert Standardwerte jeder benötigten 
        # Variablen in der Klasse.
        self.winName = "Mouth Rigger"
        self.geo_name = ""
        self.first_edge_loop = 0
        self.second_edge_loop = 0
        self.vertex_on_edge = 0
        self.lofted_surface = 0
        self.v_value = 0.5
        self.prefix = ""
        self.uValue_right_corner = 0.75
        self.uValue_left_corner = 0.25
        self.uValue_upper_corner = 0
        self.uValue_lower_corner = 0.5
        self.segments_between_corner_points = 1/4
        self.deformer_grp = 0 
        self.follicle_grp = 0
        self.binding_joint_grp = 0
        self.control_joint_grp = 0  
        self.controller_grp = 0
        self.size = 0
        self.direction_counter_clockwise = False
        

        super(ribbon_lip_rigger,self).__init__(parent)
              
        self.setWindowTitle(self.winName)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, 1)
        self.resize(400, 250)
        self.layout()
    
    # Diese Funktion definiert den Aufbau der Bedienfläche.
    def layout(self):

        # Teilt die Bedienfläche in zwei Hauptgruppen ein.
        self.user_input_group = QtWidgets.QGroupBox("User Input")
        self.finish_rig_group = QtWidgets.QGroupBox("Individualize"+
                                        " and Finish")
        

        # Erstellt das Layout für den Text zur Beschreibung 
        # der Eingabe von den Nutzenden. 
        self.user_input_text_layout = QtWidgets.QVBoxLayout()
        self.user_input_text_layout.setContentsMargins(1, 1, 1, 1)
        self.user_input_text_01 = QtWidgets.QLabel("Select two edge" + 
                                        " loops around the mouth")
        self.user_input_text_02 = QtWidgets.QLabel("Then select the"+
                                        " upper middle vertex of the"+ 
                                        " outer edge loop")
        self.user_input_text_01.setAlignment(QtCore.Qt.AlignCenter)
        self.user_input_text_02.setAlignment(QtCore.Qt.AlignCenter)
        self.user_input_text_layout.addWidget(self.user_input_text_01)
        self.user_input_text_layout.addWidget(self.user_input_text_02)


        # Erstellt das Layout für die Eingabe des Präfixes. 
        self.prefix_layout = QtWidgets.QHBoxLayout()
        self.prefix_layout.setContentsMargins(1, 1, 1, 1)
        self.prefix_titel = QtWidgets.QLabel("Prefix:", self)
        self.prefix_text = QtWidgets.QLineEdit(self)
        self.prefix_text.setText("Lip")
        self.prefix_layout.addWidget(self.prefix_titel)
        self.prefix_layout.addWidget(self.prefix_text)


        # Erstellt das Layout für die Eingabe des ersten Edge-Loops. 
        self.first_edge_loop_layout = QtWidgets.QHBoxLayout()
        self.first_edge_loop_layout.setContentsMargins(1,1,1,1)
        self.first_edge_loop_titel = QtWidgets.QLabel("First"+
                                        " Edge Loop:", self)
        self.first_edge_loop_text = QtWidgets.QLineEdit(self)
        self.first_edge_loop_text.setReadOnly(True)
        self.first_edge_loop_text.deselect()
        self.first_edge_loop_button = QtWidgets.QPushButton("<<",
                                        self)
        self.first_edge_loop_layout.addWidget\
                                    (self.first_edge_loop_titel)
        self.first_edge_loop_layout.addWidget\
                                    (self.first_edge_loop_text)
        self.first_edge_loop_layout.addWidget\
                                    (self.first_edge_loop_button)


        # Erstellt das Layout für die Eingabe des zweiten Edge-Loops. 
        self.second_edge_loop_layout = QtWidgets.QHBoxLayout()
        self.second_edge_loop_layout.setContentsMargins(1,1,1,1)
        self.second_edge_loop_titel = QtWidgets.QLabel("Second"+
                                        " Edge Loop:", self)
        self.second_edge_loop_text = QtWidgets.QLineEdit(self)
        self.second_edge_loop_text.setReadOnly(True)
        self.second_edge_loop_text.deselect()
        self.second_edge_loop_button = QtWidgets.QPushButton("<<",
                                        self)
        self.second_edge_loop_layout.addWidget\
                                    (self.second_edge_loop_titel)
        self.second_edge_loop_layout.addWidget\
                                    (self.second_edge_loop_text)
        self.second_edge_loop_layout.addWidget\
                                    (self.second_edge_loop_button)


        # Erstellt das Layout für die Eingabe des Vertexpunktes. 
        self.vertex_layout = QtWidgets.QHBoxLayout()
        self.vertex_layout.setContentsMargins(1,1,1,1)
        self.vertex_titel = QtWidgets.QLabel("Vertex:", self)
        self.vertex_text = QtWidgets.QLineEdit(self)
        self.vertex_text.setReadOnly(True)
        self.vertex_text.deselect()
        self.vertex_button = QtWidgets.QPushButton("<<", self)
        self.vertex_layout.addWidget(self.vertex_titel)
        self.vertex_layout.addWidget(self.vertex_text)
        self.vertex_layout.addWidget(self.vertex_button)


        # Erstellt das Layout für den Button, welcher 
        # die Eingabe bestätigt. 
        self.user_input_button_layout = QtWidgets.QHBoxLayout()
        self.user_input_button_layout.setContentsMargins(1,1,1,1)
        self.user_input_button = QtWidgets.QPushButton("Confirm",self)
        self.user_input_button_layout.addWidget\
                                            (self.user_input_button)


        # Verbindet alle erstellten Layouts mit
        # der ersten Hauptgruppe.
        self.user_input_layout = QtWidgets.QVBoxLayout()
        self.user_input_layout.setContentsMargins(6, 1, 6, 2)
        self.user_input_layout.addLayout(self.prefix_layout)
        self.user_input_layout.addLayout(self.user_input_text_layout)
        self.user_input_layout.addLayout(self.first_edge_loop_layout)
        self.user_input_layout.addLayout(self.second_edge_loop_layout)
        self.user_input_layout.addLayout(self.vertex_layout)
        self.user_input_layout.addLayout\
                                    (self.user_input_button_layout)
        self.user_input_group.setLayout(self.user_input_layout)


        # Erstellt das Layout für den Text zur Beschreibung 
        # der Erstellung der Zwischenjoints.
        self.finish_rig_text_01_layout = QtWidgets.QVBoxLayout()
        self.finish_rig_text_01_layout.setContentsMargins(1, 1, 1, 1)
        self.finish_rig_text_01 = QtWidgets.QLabel("Create joints in"+ 
                                        " between the ones that"+ 
                                        " already exist")
        self.finish_rig_text_01.setAlignment(QtCore.Qt.AlignCenter)
        self.finish_rig_text_01_layout.addWidget\
                                        (self.finish_rig_text_01)


        # Erstellt das Layout für den Zahlenregler.
        self.inbetween_joints_layout = QtWidgets.QHBoxLayout()
        self.inbetween_joints_layout.setContentsMargins(1,1,1,1)
        self.inbetween_joints_text = QtWidgets.QLineEdit(self)
        self.inbetween_joints_text.setText("0")
        self.inbetween_joints_text.setReadOnly(True)
        self.inbetween_joints_text.deselect()
        self.inbetween_joints_slider = QtWidgets.QSlider\
                                        (QtCore.Qt.Horizontal)
        self.inbetween_joints_slider.setValue(0)
        self.inbetween_joints_slider.setMinimum(0)
        self.inbetween_joints_slider.setMaximum(10)
        self.inbetween_joints_slider.setTickPosition\
                                    (QtWidgets.QSlider.TicksBelow)
        self.inbetween_joints_layout.addWidget\
                                    (self.inbetween_joints_text)
        self.inbetween_joints_layout.addWidget\
                                    (self.inbetween_joints_slider)


        # Erstellt das Layout für den Text, welcher die 
        # finalen Schritte erklärt.
        self.finish_rig_text_02_layout = QtWidgets.QVBoxLayout()
        self.finish_rig_text_02_layout.setContentsMargins(1, 1, 1, 1)
        self.finish_rig_text_02 = QtWidgets.QLabel("Move the joints"+
                                    " to match the desired position" )
        self.finish_rig_text_03 = QtWidgets.QLabel("If you are"+
                                    " happy, finish the rig by"+
                                    " pressing the button" )
        self.finish_rig_text_02.setAlignment(QtCore.Qt.AlignCenter)
        self.finish_rig_text_03.setAlignment(QtCore.Qt.AlignCenter)
        self.finish_rig_text_02_layout.addWidget\
                                        (self.finish_rig_text_02)
        self.finish_rig_text_02_layout.addWidget\
                                        (self.finish_rig_text_03)


        # Erstellt das Layout für den Button, welcher 
        # das Rig fertigstellt.
        self.finish_rig_button_layout = QtWidgets.QHBoxLayout()
        self.finish_rig_button_layout.setContentsMargins(1,1,1,1)
        self.finish_rig_button = QtWidgets.QPushButton("Finish",self)
        self.finish_rig_button_layout.addWidget\
                                        (self.finish_rig_button)


        # Verbindet die neu erstellten Layouts mit
        # der zweiten Hauptgruppe.
        self.finish_rig_layout = QtWidgets.QVBoxLayout()
        self.finish_rig_layout.setContentsMargins(6, 1, 6, 2)
        self.finish_rig_layout.addLayout\
                                    (self.finish_rig_text_01_layout)
        self.finish_rig_layout.addLayout\
                                    (self.inbetween_joints_layout)
        self.finish_rig_layout.addLayout\
                                    (self.finish_rig_text_02_layout)
        self.finish_rig_layout.addLayout\
                                    (self.finish_rig_button_layout) 
        self.finish_rig_group.setLayout(self.finish_rig_layout)


        # Verbindet die beiden Hauptgruppen mit dem Hauptlayout und
        # setzt dieses.
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.addWidget(self.user_input_group)
        main_layout.addWidget(self.finish_rig_group)
        self.setLayout(main_layout)
		
        # Fügt Aktionen zu den Buttons und dem Zahlenregler hinzu.
        # Diese werden ausgeführt, sobald der Button betätigt
        # oder der Wert des Zahlenreglers verändert wird.
        self.first_edge_loop_button.clicked.connect\
                                    (self.get_first_edge_loop)
        self.second_edge_loop_button.clicked.connect\
                                    (self.get_2nd_edge_loop)
        self.vertex_button.clicked.connect\
                                    (self.get_vertex_on_edge_loop)
        self.user_input_button.clicked.connect(self.user_input)
        self.inbetween_joints_slider.valueChanged.connect\
                                    (self.segment_joints)
        self.finish_rig_button.clicked.connect(self.finish_rig)

    
    # Diese Funktion erstellt den ersten Teil des Rigges.
    def user_input(self):
        
        # Speichert die eingegebenen Elemente in 
        # einer neuen Variablen.
        self.prefix = self.prefix_text.text()
        first_edge_loop = self.first_edge_Loop
        second_edge_loop = self.second_edge_Loop
        vertex_on_edge = self.vertex_on_edge

        # Erstellt die deformer_grp der Ordnerstruktur.
        self.deformer_grp = pm.group(
                                name=f"{self.prefix}_deformer_grp", 
                                empty=True, )

        # Ruft die Funktion zur Erstellung der NURBS-Kurven auf und 
        # legt diese in die deformer_grp.
        self.curve_1 = get_edge_curve(first_edge_loop, self.prefix,
                                        numCurve=1)
        self.curve_2 = get_edge_curve(second_edge_loop, self.prefix,
                                        numCurve=2)
        pm.parent(self.curve_1, self.deformer_grp)
        pm.parent(self.curve_2, self.deformer_grp)
        
        # Ruft die Funktion zur Bestimmung der benötigten Anzahl 
        # an Joints und Controllern auf.
        u_count = get_edge_count(first_edge_loop)

        # Ruft die Funktion zur Bestimmung der Größe auf.
        self.size = get_reference_size(self.curve_1, self.curve_2)

        # Ruft die Funktion zur Erstellung der NURBS-Regelfläche auf 
        # und legt diese in die deformer_grp.
        self.lofted_surface = get_lofted_surface(self.curve_1,
                                    self.curve_2, 
                                    vertex_on_edge,self.prefix)
        pm.parent(self.lofted_surface, self.deformer_grp)

        # Erstellt die Gruppen für die Follicles und
        # deformierenden Joints.
        # Die follice_grp wird in die deformer_grp gelegt.
        self.follicle_grp = pm.group(
                                name=f"{self.prefix}_follicle_grp",
                                empty=True)
        pm.parent(self.follicle_grp , self.deformer_grp)
        self.binding_joint_grp = pm.group(
                                name=f"{self.prefix}_binding_"+
                                    "joints_grp" , empty=True )

        # Ruft die Funktion zur Erstellung der Follicles und 
        # deformierenden Joints auf.
        create_surface_ribbons(self.lofted_surface, self.prefix, 
                    self.follicle_grp, self.binding_joint_grp, 
                    u_count, self.size)
        
        # Für den weiteren Verlauf werden die Elemente in 
        # der deformer_grp und der binding_joint_grp 
        # nicht gebraucht. 
        # Daher wird die Sichtbarkeit dieser verändert.
        self.deformer_grp.v.set(False)
        self.binding_joint_grp.v.set(False)
        

        # Erstellt den Hüllkörper der NURBS-Regelfläche und berechnet 
        # den mittleren Y-Wert.
        bbx = pm.exactWorldBoundingBox(self.lofted_surface)
        bbx_yAverage = (bbx[4]- bbx[1]) /2
        bbx_yResult = bbx[1] + bbx_yAverage

        # Berechnet den U-Wert für die Seiten, um die Richtung der 
        # NURBS-Regelfläche zu bestimmen.
        self.uValue_right_corner = get_corner_point(bbx[0] ,
                                        bbx_yResult, bbx[2],
                                        self.lofted_surface)
        self.uValue_left_corner = get_corner_point(bbx[3] ,
                                        bbx_yResult, bbx[2],
                                        self.lofted_surface)

        # Sollte die Richtung gegen den Uhrzeigersinn gehen, 
        # werden die U-Werte der linken und rechten Seite getauscht.
        if self.uValue_right_corner < self.uValue_left_corner:
            self.direction_counter_clockwise = True
            self.uValue_right_corner = 0.25
            self.uValue_left_corner = 0.75

        # Ruft die Funktion zur Erstellung der vier Hauptjoints auf.
        self.right_corner_joint = set_control_joints(
                                    self.uValue_right_corner,
                                    self.v_value ,
                                    self.lofted_surface,
                                    f"{self.prefix}_R" , self.size)
        self.left_corner_joint = set_control_joints(
                                    self.uValue_left_corner,
                                    self.v_value ,
                                    self.lofted_surface,
                                    f"{self.prefix}_L" , self.size)
        self.upper_corner_joint = set_control_joints(
                                    self.uValue_upper_corner,
                                    self.v_value ,
                                    self.lofted_surface,
                                    f"{self.prefix}_U" , self.size)
        self.lower_corner_joint = set_control_joints(
                                    self.uValue_lower_corner,
                                    self.v_value ,
                                    self.lofted_surface,
                                    f"{self.prefix}_D" , self.size)




    # Diese Funktion wird nach jeder Änderung des 
    # Zahlenreglers aufgerufen und erstellt die Zwischenjoints.
    def segment_joints(self, value):

        # Der aktuelle Wert des Zahlenreglers wird in
        # einer Variablen gespeichert.
        slider_value = value
        self.inbetween_joints_text.setText(str(value))

        # Um die Interaktivität zu ermöglichen, werden 
        # die Zwischenjoints in einer Gruppe gespeichert,
        # diese wird bei jedem Aufrufen dieser Funktion 
        # auf Existenz geprüft und gegebenenfalls gelöscht.
        if pm.objExists(self.control_joint_grp) == True:
            pm.delete(self.control_joint_grp)
            
        # Erstellt die Gruppe.
        self.control_joint_grp = pm.group(
                                name= f"{self.prefix}_control_"+
                                "joints_grp", empty = True )


        # Die For-Schleife iteriert für den Wert des Zahlenreglers und 
        # ruft die Funktion zur Erstellung der Joints auf. 
        for i in range (1,slider_value+1) :
        
            # Überprüft die Richtung der NURBS-Regelfläche und passt
            # die U-Werte an diese an.
            if self.direction_counter_clockwise == True :
                u_value_upper_right = (self.uValue_right_corner - 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i))
                u_value_lower_right = (self.uValue_right_corner + 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i)) 
                u_value_upper_left = (self.uValue_left_corner + 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i))
                u_value_lower_left = (self.uValue_left_corner - 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i))
            else:
                u_value_upper_right = (self.uValue_right_corner + 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i))
                u_value_lower_right = (self.uValue_right_corner - 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i)) 
                u_value_upper_left = (self.uValue_left_corner - 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i))
                u_value_lower_left = (self.uValue_left_corner + 
                        ((self.segments_between_corner_points/
                        (slider_value+1)) *i))

            
            # Ruft für jeden Bereich die Funktion zur Erstellung
            # der Joints auf.
            segmentJoint_upper_right = set_control_joints(
                                            u_value_upper_right,
                                            self.v_value,
                                            self.lofted_surface, 
                                            f",{self.prefix}_RU_{i}",
                                            self.size)
            segmentJoint_lower_right = set_control_joints(
                                            u_value_lower_right,
                                            self.v_value,
                                            self.lofted_surface,
                                            f",{self.prefix}_RD_{i}",
                                            self.size)
            segmentJoinz_upper_left = set_control_joints(
                                            u_value_upper_left, 
                                            self.v_value,
                                            self.lofted_surface ,
                                            f",{self.prefix}_LU_{i}",
                                            self.size)
            segmentJoint_lower_left = set_control_joints(
                                            u_value_lower_left, 
                                            self.v_value,
                                            self.lofted_surface,
                                            f",{self.prefix}_LD_{i}",
                                            self.size)
            
            
            # Schiebt jeden erstellten Joint in die Gruppe.
            pm.parent( segmentJoint_upper_right,
                        self.control_joint_grp)
            pm.parent( segmentJoint_lower_right,
                        self.control_joint_grp)
            pm.parent( segmentJoinz_upper_left,
                        self.control_joint_grp)
            pm.parent( segmentJoint_lower_left,
                        self.control_joint_grp)

            pm.select(clear = True)



    # Diese Funktion finalisiert das Rig.
    def finish_rig(self):

        # Die NURBS-Kurven werden gelöscht, da diese 
        # nicht mehr benötigt werden.
        pm.delete(self.curve_1)
        pm.delete(self.curve_2)

        # Überprüft, ob Zwischenjoints erstellt wurden und 
        # dadurch bereits eine Gruppe für die 
        # kontrollierenden Joints besteht. Sollte dies nicht 
        # der Fall sein, wird diese erstellt
        if pm.objExists(self.control_joint_grp) == False:
            self.control_joint_grp = pm.group(
                                name = f"{self.prefix}_control_" +
                                "joints_grp", empty = True )

        # Die vier Hauptjoints werden in diese Gruppe gelegt.
        pm.parent(self.right_corner_joint, self.control_joint_grp)
        pm.parent(self.left_corner_joint, self.control_joint_grp)
        pm.parent(self.upper_corner_joint, self.control_joint_grp)
        pm.parent(self.lower_corner_joint, self.control_joint_grp)

        # Die Hauptgruppe der Controller wird erstellt.
        self.controller_grp = pm.group(
                            name = f"{self.prefix}_controller_grp",
                            empty=True)
        
        # Alle kontrollierenden Joints werden in 
        # einer Liste gespeichert.
        selJoints = pm.ls('*_ctrl_jnt', flatten = True ,
                            recursive = True)

        # Die NURBS-Regelfläche wird an die 
        # kontrollierenden Joints geskinnt.
        pm.skinCluster(selJoints, self.lofted_surface, bindMethod = 0, 
                            toSelectedBones = True,
                            name = f"{self.prefix}_skinCluster")        

        # Die For-Schleife iteriert über die Liste der 
        # kontrollierenden Joints 
        # und ruft die Funktion zur Erstellung der Controller auf. 
        for Joints in selJoints:
           create_controller(Joints, self.controller_grp , self.size)
            
        pm.select(clear = True)
        
        # Die Funktion zur Erstellung der Abhängigkeiten zwischen 
        # den Controllern wird aufgerufen.
        create_blend_for_segment_controller(self.prefix)
        
        # Die kontrollierenden Joints werden versteckt und 
        # die deformierenden Joints wieder sichtbar gemacht, 
        # diese werden im weiteren Verlauf zum Skinning
        # der Geometrie benötigt.
        self.binding_joint_grp.v.set(True)
        self.control_joint_grp.v.set(False)

    # Diese Funktion nimmt den ersten ausgewählten Edge-Loop
    # und speichert diesen in einer Variablen.
    # Setzt den Text im Textfeld neben dem Button.
    def get_first_edge_loop(self):

        if (pm.ls(selection=True)):
            self.first_edge_Loop = pm.selected(flatten=True)
            name = ""
            for selObj in self.first_edge_Loop:
                name += selObj.name()
            
            self.first_edge_loop_text.setText(str(name))
            pm.select( clear=True )

        else:
            print("Please select an edge loop")

    # Diese Funktion nimmt den zweiten ausgewählten Edge-Loop
    # und speichert diesen in einer Variablen.
    # Setzt den Text im Textfeld neben dem Button.
    def get_2nd_edge_loop(self):

        if (pm.ls(selection=True)):
            self.second_edge_Loop = pm.selected(flatten=True)
            name = ""
            for selObj in self.second_edge_Loop:
                name += selObj.name()
            
            self.second_edge_loop_text.setText(str(name))
            pm.select( clear=True )
        else:
            print("Please select an edge loop")

    # Diese Funktion nimmt den ausgewählten Vertexpunkt und speichert 
    # diesen in einer Variablen
    # Setzt den Text im Textfeld neben dem Button.
    def get_vertex_on_edge_loop(self):

        if (pm.ls(selection=True)):
            self.vertex_on_edge = pm.selected(flatten=True)[0]
            self.vertex_text.setText(f"{self.vertex_on_edge}")
            pm.select( clear=True )

        else:
            print("Please select the vertex")
     
          
# Dies sorgt für die Ausführung des Tools.                                 
if __name__=="__main__":
    myWin = ribbon_lip_rigger()
    myWin.show()
