import React, { useState, useEffect, useRef } from 'react';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { io } from 'socket.io-client';

// Configuración de WebSocket
const socket = io('ws://localhost:3000', {
  transports: ['websocket'],
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000,
});

// Componentes de UI
const NodeStatusIndicator = ({ status }) => {
  const getStatusColor = () => {
    switch (status) {
      case 'available': return 'bg-green-500';
      case 'busy': return 'bg-yellow-500';
      case 'offline': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className={`w-3 h-3 rounded-full ${getStatusColor()}`}></div>
  );
};

const ModuleIcon = ({ type, onDragStart, onDragEnd }) => {
  const [{ isDragging }, drag] = useDrag(() => ({
    type: 'module',
    item: { type },
    collect: (monitor) => ({
      isDragging: !!monitor.isDragging(),
    }),
  }));

  return (
    <div
      ref={drag}
      className={`w-16 h-16 rounded-lg shadow-lg flex items-center justify-center cursor-move opacity-${isDragging ? '50' : '100'}`}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
    >
      {type === 'venice' && (
        <div className="text-center">
          <div className="text-blue-600 font-bold">🔍</div>
          <div className="text-xs text-gray-600">Venice OSINT</div>
        </div>
      )}
      {type === 'recon' && (
        <div className="text-center">
          <div className="text-purple-600 font-bold">🔎</div>
          <div className="text-xs text-gray-600">Recon</div>
        </div>
      )}
      {type === 'exploit' && (
        <div className="text-center">
          <div className="text-red-600 font-bold">⚡</div>
          <div className="text-xs text-gray-600">Exploit</div>
        </div>
      )}
    </div>
  );
};

const NodeCard = ({ node, onDrop, isOver }) => {
  const [{ isOver: dropOver }, drop] = useDrop(() => ({
    accept: 'module',
    drop: (item) => onDrop(node.id, item.type),
    collect: (monitor) => ({
      isOver: !!monitor.isOver(),
    }),
  }));

  return (
    <div
      ref={drop}
      className={`w-48 h-64 rounded-lg shadow-lg border-2 border-transparent transition-all duration-200 ${
        (isOver || dropOver) ? 'border-blue-500 ring-2 ring-blue-200' : ''
      }`}
    >
      <div className="p-2 flex justify-between items-center">
        <div className="text-sm font-bold">{node.name}</div>
        <NodeStatusIndicator status={node.status} />
      </div>
      <div className="p-2 h-full flex flex-col">
        <div className="flex-grow flex items-center justify-center">
          <div className="text-center">
            <div className="text-2xl">{node.id.substring(0, 6)}</div>
            <div className="text-xs text-gray-500">{node.type}</div>
          </div>
        </div>
        <div className="text-xs text-gray-500 mt-1">
          {node.location}
        </div>
      </div>
    </div>
  );
};

const TerminalStream = ({ taskId, output }) => {
  const terminalRef = useRef(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [output]);

  return (
    <div className="w-full h-64 bg-gray-900 text-green-400 p-2 rounded-lg overflow-hidden">
      <div
        ref={terminalRef}
        className="h-full overflow-y-auto whitespace-pre-wrap"
      >
        {output.map((line, index) => (
          <div key={index} className="text-xs">
            {line}
          </div>
        ))}
      </div>
    </div>
  );
};

const TacticalDashboard = () => {
  const [nodes, setNodes] = useState([]);
  const [modules, setModules] = useState(['venice', 'recon', 'exploit']);
  const [activeTask, setActiveTask] = useState(null);
  const [terminalOutput, setTerminalOutput] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);

  // Conexión WebSocket para actualización en tiempo real
  useEffect(() => {
    socket.on('connect', () => {
      console.log('Conectado al servidor WebSocket');
      socket.emit('subscribe', 'nodes');
      socket.emit('subscribe', 'tasks');
    });

    socket.on('node_update', (updatedNodes) => {
      setNodes(updatedNodes);
    });

    socket.on('task_assigned', (task) => {
      setActiveTask(task);
      setTerminalOutput([]);
    });

    socket.on('task_output', (data) => {
      if (data.taskId === activeTask?.id) {
        setTerminalOutput(prev => [...prev, data.output]);
      }
    });

    socket.on('disconnect', () => {
      console.log('Desconectado del servidor WebSocket');
    });

    return () => {
      socket.off('connect');
      socket.off('node_update');
      socket.off('task_assigned');
      socket.off('task_output');
      socket.off('disconnect');
    };
  }, [activeTask]);

  const handleDrop = (nodeId, moduleType) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node) return;

    const taskData = {
      nodeId,
      module: moduleType,
      timestamp: new Date().toISOString(),
      status: 'assigned',
    };

    socket.emit('assign_task', taskData);
    setSelectedNode(node);
  };

  const handleModuleDragStart = (moduleType) => {
    console.log(`Drag started for module: ${moduleType}`);
  };

  const handleModuleDragEnd = (moduleType) => {
    console.log(`Drag ended for module: ${moduleType}`);
  };

  return (
    <DndProvider backend={HTML5Backend}>
      <div className="min-h-screen bg-gray-100 p-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-6">Dashboard Táctico de Comandos</h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          <div className="bg-white p-4 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Módulos Disponibles</h2>
            <div className="flex space-x-4">
              {modules.map((module) => (
                <ModuleIcon
                  key={module}
                  type={module}
                  onDragStart={() => handleModuleDragStart(module)}
                  onDragEnd={() => handleModuleDragEnd(module)}
                />
              ))}
            </div>
          </div>

          <div className="bg-white p-4 rounded-lg shadow col-span-1 md:col-span-2 lg:col-span-2">
            <h2 className="text-xl font-semibold mb-4">Nodos Móviles</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
              {nodes.map((node) => (
                <NodeCard
                  key={node.id}
                  node={node}
                  onDrop={handleDrop}
                  isOver={selectedNode?.id === node.id}
                />
              ))}
            </div>
          </div>
        </div>

        {activeTask && (
          <div className="bg-white p-4 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4">Tarea Asignada</h2>
            <div className="flex flex-col md:flex-row gap-4">
              <div className="w-full md:w-1/2">
                <div className="bg-gray-100 p-4 rounded-lg">
                  <h3 className="font-bold mb-2">Detalles de la Tarea</h3>
                  <div className="text-sm">
                    <p><strong>Nodo:</strong> {selectedNode?.name || activeTask.nodeId}</p>
                    <p><strong>Módulo:</strong> {activeTask.module}</p>
                    <p><strong>Estado:</strong> {activeTask.status}</p>
                    <p><strong>Asignado:</strong> {new Date(activeTask.timestamp).toLocaleString()}</p>
                  </div>
                </div>
              </div>
              <div className="w-full md:w-1/2">
                <TerminalStream
                  taskId={activeTask.id}
                  output={terminalOutput}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </DndProvider>
  );
};

export default TacticalDashboard;